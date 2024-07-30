from bpy.types import Context
from .common import * 
from .preferences import * 
from . import lib, Layer
from bpy.props import *
from bpy.types import PropertyGroup, Panel, Operator, UIList, Scene

import bpy, threading, os, requests, json, zipfile

THREAD_SEARCHING = "thread_searching"
# thread_search:threading.Thread # progress:int
# global previews_collection
# preview_items = []
assets_lib = {}
last_search = {}

threads = {} # progress:int,
 
class MaterialItem(PropertyGroup): 
    name: StringProperty( name="Name", description="Material name", default="Untitled") 
    thumb: IntProperty( name="thumbnail", description="", default=0)

class DownloadQueue(PropertyGroup):
    asset_id : StringProperty()
    asset_attribute: StringProperty()
    file_path : StringProperty()
    alive : BoolProperty(default = False)
    file_size:IntProperty()
    progress : IntProperty(
        default = 0,
        min = 0,
        max = 100,
        description = 'Progress of the download',
        subtype = 'PERCENTAGE'
    )


def update_input_search(self, context):
    if self.input_last == self.input_search:
        print("no search:"+self.input_search)
        return
    
    self.input_last = self.input_search

    txlib = context.scene.texlib
    txlib.material_items.clear()

    if self.input_search == '':
        last_search.clear()
        return

    # cancel previous search
    if THREAD_SEARCHING in threads:
        cancel_searching(context)

    thread_search = threading.Thread(target=searching_material, args=(self.input_search,context))
    thread_search.progress = 0
    thread_search.cancel = False
    threads[THREAD_SEARCHING] = thread_search

    thread_search.start()

    self.searching_download.progress = 0
    self.searching_download.alive = True

def change_mode_asset(self, context):
    if not len(assets_lib):
        read_asset_info()
        load_previews()

    if self.mode_asset == "ONLINE":
        pass
    else:
        textures_dir = _get_textures_dir()
        tex_lis = os.listdir(textures_dir)

        _offline_files = {}
        for tx in tex_lis:
            tx_dir = os.path.join(textures_dir, tx)
            attr_lis = os.listdir(tx_dir)

            for att in attr_lis:
                attr_dir = os.path.join(tx_dir, att)
                if _texture_exist(tx, attr_dir):
                    _offline_files[tx] = assets_lib[tx] 
                    break       

        load_material_items(self.downloaded_material_items, _offline_files)

class TexLibProps(PropertyGroup):
    page: IntProperty(name="page", default= 0)
    input_search:StringProperty(name="Search", update=update_input_search)
    input_last:StringProperty()
    material_items:CollectionProperty(type= MaterialItem)
    material_index:IntProperty(default=0, name="Material index")
    downloaded_material_items:CollectionProperty(type= MaterialItem)
    downloaded_material_index:IntProperty(default=0, name="Material index")

    mode_asset:EnumProperty(
            items =  (('ONLINE', 'Online', ''), ('DOWNLOADED', 'Downloaded', '')),
            name = 'Location',
            default = 'ONLINE',
            description = 'Location of the PBR Texture.\n'
                '  Local: the assets that you have already downloaded.\n'
                '  Online: available for download on AmbientCG.com.\n',
            update=change_mode_asset
        )

    downloads:CollectionProperty(type=DownloadQueue)
    searching_download:PointerProperty(type=DownloadQueue)
    selected_download_item:IntProperty(default=0)

class TexLibAddToUcupaint(Operator, Layer.BaseMultipleImagesLayer):
    """Open Multiple Textures to Layer Ucupaint"""

    bl_label = ""
    bl_idname = "texlib.add_to_ucupaint"

    attribute:StringProperty()
    id:StringProperty()
   
    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def invoke(self, context, event):
        self.invoke_operator(context)
        return context.window_manager.invoke_props_dialog(self, width=320)
    
    def check(self, context):
        return self.check_operator(context)

    def draw(self, context):
        self.draw_operator(context)
    
    def execute(self, context):
        lib = assets_lib[self.id]
        attr_dwn = lib["downloads"][self.attribute]
        directory = attr_dwn["location"]
        import_list = os.listdir(directory)

        if not self.open_images_to_single_layer(context, directory, import_list):
            return {'CANCELLED'}

        return {'FINISHED'}

class TexLibCancelDownload(Operator):
    """Cancel downloading textures"""

    bl_label = ""
    bl_idname = "texlib.cancel"
    attribute:StringProperty()
    id:StringProperty()

    def execute(self, context:bpy.context):
        thread_id = _get_thread_id(self.id, self.attribute)
        thread = _get_thread(thread_id)

        if thread == None:
            return {'CANCELLED'}
        thread.cancel = True

        texlib:TexLibProps = context.scene.texlib
        dwn:DownloadQueue
        for dwn in texlib.downloads:
            if dwn.asset_id ==  self.id and dwn.asset_attribute == self.attribute:
                dwn.alive = False
                return {'FINISHED'}
            
        return {'CANCELLED'}

class TexLibRemoveTextureAttribute(Operator):
    """Remove existing textures"""

    bl_label = ""
    bl_idname = "texlib.remove_attribute"
    attribute:StringProperty()
    id:StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="Are you sure to remove this texture?")
 
    def execute(self, context:bpy.context):
        dir_up = _get_textures_dir() + self.id
        dir = dir_up + os.sep + self.attribute
        # print("item", self.id," | attr", self.attribute, " | file ", dir)
        # remove folder
        if os.path.exists(dir):
            for root, dirs, files in os.walk(dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(dir)

            # remove parent folder if empty
            if not os.listdir(dir_up):
                os.rmdir(dir_up)
                my_list = context.scene.texlib.downloaded_material_items
                my_list.remove(my_list.find(self.id))
            return {'FINISHED'}
        return {'CANCELLED'}
    
class TexLibDownload(Operator):
    """Download textures from source"""

    bl_label = ""
    bl_idname = "texlib.download"
    
    attribute:StringProperty()
    id:StringProperty()
    file_size:IntProperty
    file_exist:BoolProperty(default=False)

    def invoke(self, context, event):
        if self.file_exist:
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)
    
    def draw(self, context:bpy.context):
        layout = self.layout

        layout.label(text="Already downloaded. Overwrite?", icon="QUESTION")

    def execute(self, context):
        lib = assets_lib[self.id]
        attr_dwn = lib["downloads"][self.attribute]
        link = attr_dwn["link"]
        directory = attr_dwn["location"]
        file_name = os.path.join(directory, attr_dwn["fileName"])

        if not os.path.exists(directory):
            # print("make dir "+directory)
            os.makedirs(directory)

        thread_id = _get_thread_id(self.id, self.attribute)
        new_thread = threading.Thread(target=download_stream, args=(link,file_name,thread_id,))
        new_thread.progress = 0
        new_thread.cancel = False
        threads[_get_thread_id(self.id, self.attribute)] = new_thread

        new_thread.start()

        texlib = context.scene.texlib
        new_dwn:DownloadQueue = texlib.downloads.add()
        new_dwn.asset_id = self.id
        new_dwn.file_path = file_name
        new_dwn.asset_attribute = self.attribute
        new_dwn.alive = True
        new_dwn.file_size = attr_dwn["size"]
        new_dwn.progress = 0

        return {'FINISHED'}

class TexLibBrowser(Panel):
    bl_label = "Texlib Browser"
    bl_idname = "TEXLIB_PT_Browser"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Ucupaint"
    

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        texlib:TexLibProps = scene.texlib

        layout.prop(texlib, "mode_asset", expand=True)
        local_files_mode = texlib.mode_asset == "DOWNLOADED"

        if local_files_mode:
            sel_index = texlib.downloaded_material_index
            my_list = texlib.downloaded_material_items
        else:
            sel_index = texlib.material_index
            my_list = texlib.material_items

            layout.prop(texlib, "input_search")
            searching_dwn = texlib.searching_download
        
            if searching_dwn.alive:
                prog = searching_dwn.progress

                if prog >= 0:
                    row_search = layout.row()

                    if prog < 10:
                        row_search.label(text="Searching...")
                    else:
                        row_search.prop(searching_dwn, "progress", slider=True, text="Retrieving thumbnails.")
                        # row_search.label(text="Retrieving thumbnails..."+str(prog)+"%")
                    row_search.operator("texlib.cancel_search", icon="CANCEL")
                    
        # print("list", local_files_mode, ":",sel_index,"/",len(my_list))
        # print("list", local_files_mode, ":",texlib.material_index,"/",len(texlib.material_items)," | ", texlib.downloaded_material_index,"/",len(texlib.downloaded_material_items))
        if len(my_list):

            layout.separator()
            layout.label(text="Textures:")
            col_lay = layout.row()
            if local_files_mode:
                col_lay.template_list("TEXLIB_UL_Material", "material_list", texlib, "downloaded_material_items", texlib, "downloaded_material_index")
            else:
                col_lay.template_list("TEXLIB_UL_Material", "material_list", texlib, "material_items", texlib, "material_index")

            if sel_index < len(my_list):
                sel_mat:MaterialItem = my_list[sel_index]
                mat_id:str = sel_mat.name
                
                if local_files_mode:
                    del_it = col_lay.operator("texlib.remove_attributes", icon="REMOVE")
                    del_it.id = mat_id

                layout.separator()
                layout.label(text="Preview:")
                prev_box = layout.box()
                selected_mat = prev_box.column(align=True)
                selected_mat.alignment = "CENTER"
                selected_mat.template_icon(icon_value=sel_mat.thumb, scale=5.0)
                selected_mat.label(text=mat_id)
                downloads = assets_lib[mat_id]["downloads"]

                layout.separator()
                layout.label(text="Attributes:")
                for d in downloads:
                    dwn = downloads[d]
                    # row.alignment = "LEFT"
                    ukuran = round(dwn["size"] / 1000000,2)
                    lokasi = dwn["location"]
                    
                    check_exist:bool = _texture_exist(mat_id, lokasi)

                    # if local_files_mode and not check_exist:
                    #     continue

                    ui_attr = layout.split(factor=0.7)

                    row = ui_attr.row()

                    row.label(text=d, )
                    # rr.label(text=d, )
                    row.label(text=str(ukuran)+ "MB")

                    thread_id = _get_thread_id(mat_id, d)
                    dwn_thread = _get_thread(thread_id)

                    btn_row = ui_attr.row()
                    btn_row.alignment = "RIGHT"

                    if dwn_thread != None:
                        btn_row.label(text=str(dwn_thread.progress)+"%")
                        op:TexLibCancelDownload = btn_row.operator("texlib.cancel", icon="X")
                        op.attribute = d
                        op.id = mat_id
                    else:
                        if check_exist:
                            op:TexLibAddToUcupaint = btn_row.operator("texlib.add_to_ucupaint", icon="ADD")
                            op.attribute = d
                            op.id = sel_mat.name

                            op_remove:TexLibRemoveTextureAttribute = btn_row.operator("texlib.remove_attribute", icon="REMOVE")
                            op_remove.attribute = d
                            op_remove.id = sel_mat.name

                        op:TexLibDownload = btn_row.operator("texlib.download", icon="IMPORT")
                        op.attribute = d
                        op.id = sel_mat.name
                        op.file_exist = check_exist

            if len(texlib.downloads):
                layout.separator()
                layout.label(text="Downloads:")
                layout.template_list("TEXLIB_UL_Downloads", "download_list", texlib, "downloads", texlib, "selected_download_item")

class TEXLIB_UL_Downloads(UIList):

    def draw_item(self, context, layout, data, item:DownloadQueue, icon, active_data, active_propname, index):
        """Demo UIList."""
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            if item.alive:
                row.prop(item, "progress", slider=True, text=item.asset_id+" | "+item.asset_attribute)
                op:TexLibCancelDownload = row.operator("texlib.cancel", icon="X")  
                op.attribute = item.asset_attribute
                op.id = item.asset_id
            else:
                row.label(text="cancelling")

class TEXLIB_UL_Material(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        """Demo UIList."""

        row = layout.row(align=True)
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row.template_icon(icon_value = item.thumb, scale = 1.0)
            row.label(text=item.name)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon_value = item.thumb)

class TexLibCancelSearch(Operator):
    bl_idname = "texlib.cancel_search"
    bl_label = ""
    
    def execute(self, context):
        cancel_searching(context)
        return{'FINISHED'}
    
class TexLibRemoveTextureAllAttributes(Operator):
    bl_idname = "texlib.remove_attributes"
    bl_label = ""
    id:StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="Are you sure to remove this textures?")
 
    def execute(self, context:bpy.context):
        dir = _get_textures_dir() + self.id 
        print("item", self.id, " | file ", dir)
        my_list = context.scene.texlib.downloaded_material_items
        my_list.remove(my_list.find(self.id))
        # remove folder
        if os.path.exists(dir):
            for root, dirs, files in os.walk(dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(dir)
            return {'FINISHED'}
        
        return {'CANCELLED'}
    
def cancel_searching(context):
    thread_search = threads[THREAD_SEARCHING]
    thread_search.cancel = True
    texlib = context.scene.texlib
    
    searching_dwn = texlib.searching_download
    searching_dwn.alive = False

def load_material_items(material_items, list_tex):
    material_items.clear()
    for i in list_tex:
        new_item:MaterialItem = material_items.add()
        item_id =  list_tex[i]["id"]
        new_item.name = item_id
        if hasattr(previews_collection, "preview_items") and item_id in previews_collection.preview_items:
            new_item.thumb = previews_collection.preview_items[item_id][3]
        else:
            new_item.thumb = lib.custom_icons["input"].icon_id

def load_per_material(file_name:str, material_item):
    item = os.path.basename(file_name)

    my_id = item.split(".")[0]
    # print(">>item",item,"file",file_name, "my_id", my_id)
    loaded = previews_collection.load(item, file_name, 'IMAGE', force_reload=True)

    previews_collection.preview_items[my_id] = (my_id, item, "", loaded.icon_id, len(previews_collection.preview_items))
    material_item.thumb = loaded.icon_id

    
def searching_material(keyword:str, context:Context):
    scene = context.scene
    txlib:TexLibProps = scene.texlib

    thread_search = threads[THREAD_SEARCHING]

    if not len(assets_lib):
        read_asset_info()

    retrieve_assets_info(keyword)
    thread_search.progress = 10
    load_material_items(txlib.material_items, last_search)

    download_previews(False, txlib.material_items)
    thread_search.progress = 90
    load_previews()
    thread_search.progress = 95

    load_material_items(txlib.material_items, last_search)
    thread_search.progress = 100

def load_previews():
    # print(">>>>>>>>>>>>>>>>>>>>>>> INIT TexLIB")
    dir_name = _get_preview_dir()
    files = os.listdir(dir_name)
    
    previews_collection.clear()
    preview_items = {}
    for index, item in enumerate(files):
        file = dir_name + item
        my_id = item.split(".")[0]
        sizefile = os.path.getsize(file)
        # print(">>item",item,"file",file,"size", sizefile)
        if sizefile == 0: # detect corrupt image
            os.remove(file)
            continue
        loaded = previews_collection.load(item, file, 'IMAGE', force_reload=True)
        preview_items[my_id] = (my_id, item, "", loaded.icon_id, index)

    previews_collection.preview_items.update(preview_items)

def monitor_downloads():
        
    searching = False
    if THREAD_SEARCHING in threads:
        thread_search = threads[THREAD_SEARCHING]
        searching = True

    if not hasattr(bpy, 'context'):
        print("no context")
        return 2

    scn = bpy.context.scene
    txlb:TexLibProps = scn.texlib
    downloads = txlb.downloads

    if len(downloads) == 0 and not searching:
        # print("KOSONG")
        return 2
    
    if searching:
        prog_search = thread_search.progress
        txlb.searching_download.progress = prog_search
        if thread_search.progress >= 100:
            txlb.searching_download.alive = False

        if not thread_search.is_alive():
            del threads[THREAD_SEARCHING]
    
    # print("downloadku", len(downloads))
    # for index, dwn in enumerate(downloads):
    #     print("cek aja",dwn.asset_id," | ",dwn.asset_attribute)
    
    if len(downloads):
        to_remove = []
        dwn:DownloadQueue
        for index, dwn in enumerate(downloads):
            
            thread_id = _get_thread_id(dwn.asset_id, dwn.asset_attribute)
            thread = _get_thread(thread_id)
            if thread == None:
                print("thread id", thread_id, ">",dwn.asset_id,">", dwn.asset_attribute)
                extract_file(dwn.file_path)
                delete_zip(dwn.file_path)
                to_remove.append(index)

            else:
                prog =  thread.progress

                dwn.progress = prog
                if thread.progress >= 100:
                    dwn.alive = False

                if not thread.is_alive():
                    del threads[thread_id]

        for i in to_remove:
            downloads.remove(i)

    for window in bpy.context.window_manager.windows:
        # print("==============windoss ", window)
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for reg in area.regions:
                    # print("region",reg.type, "width", reg.width)
                    open_tab = reg.width > 1
                    if reg.type == "UI" and open_tab:
                        # print("redraw area", area.type, "reg", reg.type)
                        reg.tag_redraw()
                        return 0.1

    return 1.0

def extract_file(my_file:str) -> bool:
    dir_name = os.path.dirname(my_file)
    # new_folder = os.path.basename(my_file).split('.')[0]
    # dir_name = os.path.join(dir_name, new_folder)
    print("extract "+my_file+" to "+dir_name)

    try:
        with zipfile.ZipFile(my_file, 'r') as zObject:
            zObject.extractall(path=dir_name)
            return True    
    except zipfile.BadZipFile:
        return False

# Delete the zip file
def delete_zip(file_path):
    if not os.path.exists(file_path):
        return
    try:
        os.remove(file_path)
    except Exception as e:
        print('Error while deleting zip file:', e)

def download_stream(link:str, file_name:str, thread_id:str,
                    timeout:int = 10,skipExisting:bool = False):
    # print("url = ",link, "filename", file_name)

    thread = _get_thread(thread_id)
    
    prog = 0
    with open(file_name, "wb") as f:
        try:
            response = requests.get(link, stream=True, timeout = timeout)
            # session seems to be a little bit faster
            #session = requests.Session()
            #response = session.get(link, stream=True, timeout = timeout)
            total_length = response.headers.get('content-length')
            print("total size = "+total_length)
            if not total_length:
                print('Error #1 while downloading', link, ':', "Empty Response.")
                return
            
            dl = 0
            total_length = int(total_length)
            # TODO a way for calculating the chunk size
            for data in response.iter_content(chunk_size = 4096):
                if thread is not None and thread.cancel:
                    response.close()
                    break

                dl += len(data)
                f.write(data)
                
                prog = int(100 * dl / total_length)
                # dl_threads[0].progress = prog
                thread.progress = prog
                # print("proggg "+str(prog)+"%  "+str(dl)+"/"+str(total_length))
            # dl_threads.pop(0)
        except Exception as e:
            print('Error #2 while downloading', link, ':', e)

def download_previews(overwrite_existing:bool, material_items):
    directory = _get_preview_dir()
    if not os.path.exists(directory):
        os.mkdir(directory)
    thread_search = threads[THREAD_SEARCHING]
    
    progress_initial = thread_search.progress
    progress_max = 90
    span = progress_max - progress_initial
    item_count = len(last_search)

    for index,ast in enumerate(last_search):
        if thread_search.cancel:
            break
        link = last_search[ast]["preview"]
        file_name = bpy.path.basename(link)
        file_name = os.path.join(directory, file_name)
        
        if not overwrite_existing and os.path.exists(file_name):
            continue
        with open(file_name, "wb") as f:
            try:
                response = requests.get(link, stream=True)
                total_length = response.headers.get('content-length')
                if not total_length:
                    print('Error #1 while downloading', link, ':', "Empty Response.")
                    return
                dl = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size = 4096):
                    if thread_search is not None and thread_search.cancel:
                        response.close()
                        return
                    dl += len(data)
                    f.write(data)                    
            except Exception as e:
                print('Error #2 while downloading', link, ':', e)
        prog = (index + 1) / item_count
        # print("url = ",prog, ' | ',link,' | ', file_name)
        # refresh list
        load_per_material(file_name, material_items[index])

        thread_search.progress = (int) (progress_initial + prog * span)

def read_asset_info() -> bool:
    dir_name = _get_lib_dir()
    file_name = os.path.join(dir_name, "lib.json")

    if os.path.exists(file_name):
        file = open(file_name, 'r')
        content = file.read()
        jsn = json.loads(content)
        assets_lib.update(jsn)
        file.close()
        # print("read ", content)
        return True
    return False

def retrieve_assets_info(keyword:str = '', save_ori:bool = False, page:int = 0, limit:int = 100):
    base_link = "https://ambientCG.com/api/v2/full_json"
    params = {
        'type': 'Material',
        'include':'imageData,downloadData',
        'limit': str(limit),
        'offset': str(limit * page) 
    }

    if keyword != '':
        params['q'] = keyword
    
    dir_name = _get_lib_dir()
    file_name = os.path.join(dir_name, "lib.json")

    response = requests.get(base_link, params=params, verify=False)
    if not response.status_code == 200:
        print("Can't download, Code: " + str(response.status_code))
        return None
    
    assets = response.json()["foundAssets"]

    print("Found ",len(assets), "textures")
    
    file = open(file_name, 'w')

    # assets_lib = {}
    last_search.clear()

    tex_directory = _get_textures_dir()
    
    
    for asst in assets:
        asset_obj = {}
        asset_id = asst["assetId"]
        asset_obj["id"] = asset_id
        asset_obj["preview"] = asst["previewImage"]["256-PNG"]

        zip_assets = asst["downloadFolders"]["default"]["downloadFiletypeCategories"]["zip"]["downloads"]


       

        downloads = {}
        for k in zip_assets:
            location = os.path.join(asset_id, k["attribute"])
            directory = os.path.join(tex_directory, location)

            downloads[k["attribute"]] = {
                "link" : k["downloadLink"],
                "fileName" : k["fileName"],
                "location" : directory+os.sep,
                "size" : k["size"]
            }
        asset_obj["downloads"] = downloads
        assets_lib[asset_id] = asset_obj
        last_search[asset_id] = asset_obj

    file.write(json.dumps(assets_lib))
    file.close()
    print("stored to ", file_name)
    # print("content to ", str(assets_lib))

    if save_ori:
        file_name_ori = os.path.join(dir_name, "lib-ori.json")
        file_ori = open(file_name_ori, 'w')
        file_ori.write(json.dumps({"foundAssets":assets}))
        file_ori.close()

def _texture_exist(asset_id:str, location:str) -> bool:
    if os.path.exists(location):
        files = os.listdir(location)
        for f in files:
            if asset_id in f:
                return True
    
    return False

def _get_textures_dir() -> str:
    file_path = _get_lib_dir()
    retval = os.path.join(file_path, "textures") + os.sep
    if not os.path.exists(retval):
        os.mkdir(retval)
    return retval

def _get_preview_dir() -> str:
    file_path = _get_lib_dir()
    retval = os.path.join(file_path, "previews") + os.sep
    if not os.path.exists(retval):
        os.mkdir(retval)
    return retval

def _get_lib_dir() -> str:
    ypup:YPaintPreferences = get_user_preferences()
    retval = ypup.library_location
    if not os.path.exists(retval):
        os.mkdir(retval)
    return retval

def _get_thread_id(asset_id:str, asset_attribute:str):
    return asset_id+"_"+asset_attribute

def _get_thread(id:str):
    if id in threads: 
        return threads[id]
    return None

classes = [DownloadQueue,  MaterialItem, TexLibProps, TexLibBrowser, TexLibDownload, TexLibRemoveTextureAttribute, TexLibRemoveTextureAllAttributes, 
           TexLibAddToUcupaint, TexLibCancelDownload, TEXLIB_UL_Material,TexLibCancelSearch, TEXLIB_UL_Downloads]

def register():
    for cl in classes:
        bpy.utils.register_class(cl)

    Scene.texlib = PointerProperty(type= TexLibProps)

    global previews_collection
    previews_collection = bpy.utils.previews.new()
    previews_collection.preview_items = {}
    # load_previews()

    bpy.app.timers.register(monitor_downloads, first_interval=1, persistent=True)    

def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
    del bpy.types.Scene.texlib

    bpy.utils.previews.remove(previews_collection)

    if bpy.app.timers.is_registered(monitor_downloads):
        bpy.app.timers.unregister(monitor_downloads)

if __name__ == "__main__":
    register()