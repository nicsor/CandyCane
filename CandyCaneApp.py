#!/usr/bin/python3

import wx
import wx.html2
#import wx.html
import wx.lib.mixins.listctrl

import os
import random
import signal

import hashlib
import pathlib

from helper import Sql

class MyFrame(wx.Frame, wx.lib.mixins.listctrl.ColumnSorterMixin):
    def __init__(self, *args, **kwds):
        wx.Frame.__init__(self, *args, **kwds)

        # Open the database in memory by default
        self.sql = Sql("database.db")
        self.current_path = ""
        self.itemDataMap = {}
  
        # Menu
        #  ----------------------------------------
        menu_bar = wx.MenuBar()

        # Import menu item
        menu_it_file = wx.Menu()
        menu_it_file_save_db = menu_it_file.Append(wx.ID_ANY, "&Save database as ...")
        menu_it_file_load_db = menu_it_file.Append(wx.ID_ANY, "&Load database")
        menu_bar.Append(menu_it_file, "&File")
        self.Bind(wx.EVT_MENU, self.OnSaveDatabase, menu_it_file_save_db)
        self.Bind(wx.EVT_MENU, self.OnLoadDatabase, menu_it_file_load_db)

        # Import menu item
        menu_it_import = wx.Menu()
        menu_it_import_eml = menu_it_import.Append(wx.ID_ANY, "EML", "E-mail")
        menu_bar.Append(menu_it_import, "Import")
        self.Bind(wx.EVT_MENU, self.OnImportEml, menu_it_import_eml)

        # Finish setting up the menu bar
        self.SetMenuBar(menu_bar)

        # Main view layout
        #  ----------------------------------------
        #  -       -                              -
        #  -   C   -         Messages List        -
        #  -   a   --------------------------------
        #  -   t   -                              -
        #  -   e   -                              -
        #  -   g   -                              -
        #  -   o   -         Message Body         -
        #  -   r   -                              -
        #  -   i   -                              -
        #  -   e   -                              -
        #  -   s   --------------------------------
        #  -       -         Attachements         -
        #  ----------------------------------------
        self.layout_main = wx.SplitterWindow(self, wx.ID_ANY)

        # Split "Categories" from "Messages List" / "Message" / "Attachements"
        self.layout_left_pane = wx.Panel(self.layout_main, wx.ID_ANY)
        self.layout_right_pane = wx.Panel(self.layout_main, wx.ID_ANY)

        self.layout_content = wx.SplitterWindow(self.layout_right_pane, wx.ID_ANY)

        # Split "Messages List" from "Message"
        self.layout_msg_list_pane = wx.Panel(self.layout_content, wx.ID_ANY)
        self.layout_msg_body_pane = wx.Panel(self.layout_content, wx.ID_ANY)

        # Attachements
        self.layout_attachment_pane = wx.StaticBox(
             self.layout_right_pane, wx.ID_ANY, "Attachments")

        # Panels
        #  ----------------------------------------

        # Categories panel
        self.tree_categories = wx.TreeCtrl(self.layout_left_pane, wx.ID_ANY)
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.onCategorySelected, self.tree_categories)

        # Messages list
        self.ctrl_messages_list = wx.ListCtrl(
             self.layout_msg_list_pane, wx.ID_ANY, style=wx.LC_HRULES | wx.LC_REPORT | wx.LC_VRULES)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.onMessageSelected, self.ctrl_messages_list)

        # Message body
        self.ctrl_message_content = wx.html2.WebView.New(self.layout_msg_body_pane, id=wx.ID_ANY)
        #self.ctrl_message_content = wx.html.HtmlWindow(self.layout_msg_body_pane, id=wx.ID_ANY)

        # Attachments panel
        self.combo_attachments = wx.ComboBox(self.layout_right_pane, wx.ID_ANY)
        self.btn_download = wx.Button(self.layout_right_pane, wx.ID_ANY, "Download")
        self.Bind(wx.EVT_BUTTON, self.onAttachmentDownload, self.btn_download)

        # Filters
        self.txt_filter_receivers = wx.TextCtrl(self.layout_left_pane, wx.ID_ANY, "")
        self.txt_filter_sender = wx.TextCtrl(self.layout_left_pane, wx.ID_ANY, "")
        self.txt_filter_subject = wx.TextCtrl(self.layout_left_pane, wx.ID_ANY, "")
        self.txt_filter_content = wx.TextCtrl(self.layout_left_pane, wx.ID_ANY, "")
        self.btn_filter = wx.Button(self.layout_left_pane, wx.ID_ANY, "Refresh")
        self.btn_filter_clear = wx.Button(self.layout_left_pane, wx.ID_ANY, "Clear")
        self.Bind(wx.EVT_BUTTON, self.onFilterActivated, self.btn_filter)
        self.Bind(wx.EVT_BUTTON, self.onFilterCleared, self.btn_filter_clear)

        self.__set_properties()
        self.__set_stretching_info()

        self.Layout()
        self.OnDatabseUpdate()

    def OnExportEml(self, e):
        print("OnExportEml")
        self.Close()

    def OnImportEml(self, e):
        print("OnImportEml")

        dirname = ""
        dlg = wx.DirDialog(self, message="Choose emails folder")
 
        if dlg.ShowModal() == wx.ID_OK:
            dirname = dlg.GetPath()
            print(dirname)

            for path in pathlib.Path(dirname).rglob('*.eml'):
                emailFile = str(path)
                emailFileMeta = emailFile + ".meta"

                self.sql.addEMLEntry(emailFile, emailFileMeta)

            print("Done parsing: " + str(dirname))
            self.OnDatabseUpdate()

        dlg.Destroy()

    def OnLoadDatabase(self, e):
        print("OnLoadDatabase")

        try:
            dlg = wx.FileDialog(self, "Load database from file", ".", "", "Sqlite databse (*.db)|*.db", wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
            if (dlg.ShowModal() == wx.ID_OK):
                filename = dlg.GetFilename()
                dirname = dlg.GetDirectory()
                file = os.path.join(dirname, filename)
                self.sql = Sql(str(file))

                self.OnDatabseUpdate()

            dlg.Destroy()
        except Exception as e:
            print("Could not load the database: " + str(e))
            pass

    def OnSaveDatabase(self, e):
        print("OnSaveDatabase")

        try:
            dlg = wx.FileDialog(self, "Save database to file", ".", "database.db", "Sqlite databse (*.db)|*.db", wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
            if (dlg.ShowModal() == wx.ID_OK):
                filename = dlg.GetFilename()
                dirname = dlg.GetDirectory()
                filePath = str(os.path.join(dirname, filename))
                self.sql.saveToFile(filePath)
            dlg.Destroy()
        except Exception as e:
            print("Could not save the database: " + str(e))
            pass

    def __set_properties(self):
        self.SetTitle("CandyCane")
        self.ctrl_messages_list.AppendColumn("Id", format=wx.LIST_FORMAT_LEFT, width=0)
        self.ctrl_messages_list.AppendColumn("From", format=wx.LIST_FORMAT_LEFT, width=400)
        self.ctrl_messages_list.AppendColumn("To", format=wx.LIST_FORMAT_LEFT, width=400)
        self.ctrl_messages_list.AppendColumn("Subject", format=wx.LIST_FORMAT_LEFT, width=450)
        self.ctrl_messages_list.AppendColumn("Date", format=wx.LIST_FORMAT_LEFT, width=200)
        self.ctrl_messages_list.AppendColumn("Attachments", format=wx.LIST_FORMAT_LEFT, width=500)

        # initialize the column sorter
        wx.lib.mixins.listctrl.ColumnSorterMixin.__init__(self, 6)

        if "gtk2" in wx.PlatformInfo: 
            self.ctrl_message_content.SetStandardFonts() 

    def __set_stretching_info(self):
        self.SetMinSize(wx.Size(800,600))

        rightPane = wx.BoxSizer(wx.VERTICAL)

        # Messages list pane
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.ctrl_messages_list, 1, wx.EXPAND, 0)
        self.layout_msg_list_pane.SetSizer(sizer)

        # Message body pane
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.ctrl_message_content, 1, wx.EXPAND, 0)
        self.layout_msg_body_pane.SetSizer(sizer)

        # Attachements pane
        attachmentPane = wx.StaticBoxSizer(self.layout_attachment_pane, wx.HORIZONTAL)
        attachmentPane.Add(self.combo_attachments, 1, 0, 0)
        attachmentPane.Add(self.btn_download, 1, 0, 0)

        # Content Layout
        self.layout_content.SetSashGravity(0.2)
        self.layout_content.SplitHorizontally(self.layout_msg_list_pane, self.layout_msg_body_pane)
        rightPane.Add(self.layout_content, 1, wx.EXPAND, 0)
        rightPane.Add(attachmentPane, 0, wx.EXPAND, 0)
        self.layout_right_pane.SetSizer(rightPane)

        # Category Pane
        categoryPane = wx.BoxSizer(wx.VERTICAL)
        categoryPane.Add(self.tree_categories, 1, wx.EXPAND, 0)
        self.layout_left_pane.SetSizer(categoryPane)

        # Filter Pane
        filterPane = wx.BoxSizer(wx.VERTICAL)

        filterReceiversPane = wx.StaticBoxSizer(
            wx.StaticBox(self.layout_left_pane, wx.ID_ANY, "To"), wx.HORIZONTAL)
        filterReceiversPane.Add(self.txt_filter_receivers, 1, wx.EXPAND, 0)
        filterPane.Add(filterReceiversPane, 0, wx.EXPAND, 0)

        filterSenderPane = wx.StaticBoxSizer(
            wx.StaticBox(self.layout_left_pane, wx.ID_ANY, "From"), wx.HORIZONTAL)
        filterSenderPane.Add(self.txt_filter_sender, 1, wx.EXPAND, 0)
        filterPane.Add(filterSenderPane, 0, wx.EXPAND, 0)

        filterSubjectPane = wx.StaticBoxSizer(
            wx.StaticBox(self.layout_left_pane, wx.ID_ANY, "Subject"), wx.HORIZONTAL)
        filterSubjectPane.Add(self.txt_filter_subject, 1, wx.EXPAND, 0)
        filterPane.Add(filterSubjectPane, 0, wx.EXPAND, 0)

        filterContentPane = wx.StaticBoxSizer(
            wx.StaticBox(self.layout_left_pane, wx.ID_ANY, "Content"), wx.HORIZONTAL)
        filterContentPane.Add(self.txt_filter_content, 1, wx.EXPAND, 0)
        filterPane.Add(filterContentPane, 0, wx.EXPAND, 0)

        filterActionPane = wx.GridSizer(0, 2, 0, 0)
        filterActionPane.Add(self.btn_filter, 1, wx.EXPAND, 0)
        filterActionPane.Add(self.btn_filter_clear, 1, wx.EXPAND, 0)
        filterPane.Add(filterActionPane, 0, wx.EXPAND, 0)

        categoryPane.Add(filterPane, 0, wx.EXPAND, 0)

        # Main layout
        self.layout_main.SetMinimumPaneSize(100)
        self.layout_main.SetSashGravity(0.2)
        self.layout_main.SplitVertically(self.layout_left_pane, self.layout_right_pane)
        self.layout_main.SetSashPosition(100, 1)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.layout_main, 1, wx.EXPAND, 0)
        self.SetSizer(sizer)
 
    def onMessageSelected(self, event):
        hash = self.ctrl_messages_list.GetItem(event.GetIndex(), 0).GetText()
        #html = str(self.sql.getContent(hash)).encode('latin-1')
        html = self.sql.getContent(hash)

        # Load the selected page
        try:
            self.ctrl_message_content.SetPage(html, "")
        except:
            print("Problem interpreting charset. Lazy workaround: Trying latin-1")
            html = html.decode('latin-1')
            self.ctrl_message_content.SetPage(html, "")

        attachments = self.sql.getAttachements(hash)
        self.setAttachments(attachments)

        event.Skip()

    def setAttachments(self, entries):
        self.combo_attachments.Clear()

        for item in entries:
            self.combo_attachments.Append(item)

        if len(entries) == 0:
           self.combo_attachments.Enable(False)
           self.btn_download.Enable(False)
        else:
           self.combo_attachments.SetSelection(0)
           self.combo_attachments.Enable(True)
           self.btn_download.Enable(True)

    def getStubbedAttachments(self):
        n = random.randint(0,10)
        randomlist = random.sample(range(10, 30), n)
        randomStringlist = list(map(str, randomlist))
        return randomStringlist

    def onCategorySelected(self, event):
        previous = ""
        cale = ""
        curent = event.GetItem()
        while (curent.IsOk()):
           # Don't include the root node
           cale = previous + cale
 
           previous = "/" + str(self.tree_categories.GetItemText(curent))
           curent = self.tree_categories.GetItemParent(curent)

        self.current_path = cale
        print(cale)

        self.OnDatabseUpdate(True)

        event.Skip()

    def onAttachmentDownload(self, event):
        index = self.ctrl_messages_list.GetNextItem(-1,
                            wx.LIST_NEXT_ALL,
                            wx.LIST_STATE_SELECTED)
        if index == -1:
            event.Skip()
            return

        hash = self.ctrl_messages_list.GetItem(index, 0).GetText()
        file = self.combo_attachments.GetStringSelection()

        if (hash != "" and file != ""):
            try:
                dlg = wx.FileDialog(self, "Save to file:", ".", file, "Sqlite databse (*.db)|*.db", wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
                if (dlg.ShowModal() == wx.ID_OK):
                    filename = dlg.GetFilename()
                    dirname = dlg.GetDirectory()
                    filePath = str(os.path.join(dirname, filename))
                    print(self.sql.getCategories())
                    self.sql.downloadAttachment(hash, file, filePath)
                dlg.Destroy()
            except Exception as e:
                print("Could not save the file: " + str(e))
                pass

        event.Skip()

    def onFilterActivated(self, event):
        self.OnDatabseUpdate()

    def onFilterCleared(self, event):
        self.txt_filter_receivers.SetValue("")
        self.txt_filter_sender.SetValue("")
        self.txt_filter_subject.SetValue("")
        self.txt_filter_content.SetValue("")
        self.OnDatabseUpdate()

    def addCategories(self, root, categories):
        for category in categories:
            item = self.tree_categories.AppendItem(root, category)
            self.addCategories(item, categories[category])

    def onCategoriesUpdate(self, categories):
        categoriesOverview = {}
        for category in categories:
            subPaths = category.split('/')
            currentEntry = categoriesOverview
            for subPath in subPaths:
                if subPath == "":
                    continue
                if subPath not in currentEntry:
                    currentEntry[subPath] = {}
                currentEntry = currentEntry[subPath]

        self.tree_categories.DeleteAllItems()
        root = self.tree_categories.AddRoot('/')
        self.addCategories(root, categoriesOverview)
        self.tree_categories.ExpandAll()

    def onMessageListUpdate(self, messages):
        self.ctrl_messages_list.DeleteAllItems()
        self.itemDataMap.clear()

        for item in messages:
            dataTuple = [item[0], item[1], item[2], item[3], item[4], item[5]]
            index = self.ctrl_messages_list.Append(dataTuple)

            self.ctrl_messages_list.SetItemData(index, index)
            self.itemDataMap[index] = item

    def OnDatabseUpdate(self, skipCategories = False):
        if not skipCategories:
           # We won't filter categories, although we could
           self.onCategoriesUpdate(self.sql.getCategories())
        self.onMessageListUpdate(
           self.sql.getEnries(
               path = self.current_path,
               receivers = self.txt_filter_receivers.GetValue(),
               sender = self.txt_filter_sender.GetValue(),
               subject = self.txt_filter_subject.GetValue(),
               content = self.txt_filter_content.GetValue()))

    def GetListCtrl(self):
        return self.ctrl_messages_list

class MyApp(wx.App):


    def OnInit(self):
        self.dialog = MyFrame(None, wx.ID_ANY, "", style =  wx.DEFAULT_FRAME_STYLE | wx.MAXIMIZE)
        self.SetTopWindow(self.dialog)
        self.dialog.Show()

        return True

def sig_handler(signum, frame):
    print("OH noooooooooo there is no cheesburger!")

if __name__ == "__main__":
    #wx.Log.SetActiveTarget(wx.LogNull)
    wx.Log.EnableLogging(False)
    signal.signal(signal.SIGSEGV, sig_handler)
    app = MyApp(0)
    app.MainLoop()
