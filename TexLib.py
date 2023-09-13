from bpy.types import Context
from .common import * 
from .lib import *
from zipfile import ZipFile

import bpy, threading, os, requests, json
from bpy.props import *
from bpy.types import PropertyGroup, Panel, Operator, UIList, Scene

THREAD_SEARCHING = "thread_searching"
# thread_search:threading.Thread # progress:int
# global previews_collection
# preview_items = []
assets_lib = {}
last_search = {}

threads = {} # progress:int,

def update_input_search(self, context):
    if self.input_last == self.input_search:
        print("no search:"+self.input_search)
        return
    
    self.input_last = self.input_search

    context.scene.material_items.clear()

    if self.input_search == '':
        last_search.clear()
        return

    thread_search = threading.Thread(target=searching_material, args=(self.input_search,context))
    thread_search.progress = 0
    thread_search.cancel = False
    threads[THREAD_SEARCHING] = thread_search

    thread_search.start()

    self.searching_download.progress = 0
    self.searching_download.alive = True
    
def searching_material(keyword:str, context:Context):
    scene = context.scene

    thread_search = threads[THREAD_SEARCHING]

    retrieve_assets_info(keyword)
    thread_search.progress = 10
    load_material_items(scene.material_items)

    download_previews(False, scene.material_items)
    thread_search.progress = 90
    load_previews()
    thread_search.progress = 95


    load_material_items(scene.material_items)
    # scene.material_items.clear()
    # for i in last_search:
    #     new_item = scene.material_items.add()
    #     item_id =  last_search[i]["id"]
    #     new_item.name = item_id
    #     # new_item.thumb = lib.custom_icons["input"].icon_id # previews_collection.preview_items[item_id][3]
    #     new_item.thumb = previews_collection.preview_items[item_id][3]
    thread_search.progress = 100

    print("finish search")

def load_material_items(material_items):
    material_items.clear()
    for i in last_search:
        new_item = material_items.add()
        item_id =  last_search[i]["id"]
        new_item.name = item_id
        if hasattr(previews_collection, "preview_items") and item_id in previews_collection.preview_items:
            new_item.thumb = previews_collection.preview_items[item_id][3]
        else:
            new_item.thumb = lib.custom_icons["input"].icon_id

def load_per_material(file_name, material_item):
    item = os.path.basename(file_name)

    my_id = item.split(".")[0]
    # print(">>item",item,"file",file_name, "my_id", my_id)
    loaded = previews_collection.load(item, file_name, 'IMAGE', force_reload=True)

    previews_collection.preview_items[my_id] = (my_id, item, "", loaded.icon_id, len(previews_collection.preview_items))
    material_item.thumb = loaded.icon_id

class DownloadThread(PropertyGroup):
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

class TexLibProps(bpy.types.PropertyGroup):
    page: IntProperty(name="page", default= 0)
    input_search:StringProperty(name="Search", update=update_input_search)
    input_last:StringProperty()
    downloads:CollectionProperty(type=DownloadThread)
    searching_download:PointerProperty(type=DownloadThread)
    selected_download_item:IntProperty(default=0)


class TexLibDownload(Operator):
    bl_label = "Download"
    bl_idname = "texlib.download"
    

    attribute:StringProperty()
    id:StringProperty()
    file_size:IntProperty

    def execute(self, context):
       
        lib = assets_lib[self.id]
        attr_dwn = lib["downloads"][self.attribute]
        link = attr_dwn["link"]
        directory = attr_dwn["location"]
        file_name = os.path.join(directory, attr_dwn["fileName"])

        print("setar =",self.attribute, "selected = "+self.id, "lib =", link)

        if not os.path.exists(directory):
            # print("make dir "+directory)
            os.makedirs(directory)

        thread_id = _get_thread_id(self.id, self.attribute)
        new_thread = threading.Thread(target=download_stream, args=(link,file_name,thread_id,))
        new_thread.progress = 0
        new_thread.cancel = False
        threads[_get_thread_id(self.id, self.attribute)] = new_thread

        new_thread.start()

        amb_br = context.scene.ambient_browser
        new_dwn:DownloadThread = amb_br.downloads.add()
        new_dwn.asset_id = self.id
        new_dwn.file_path = file_name
        new_dwn.asset_attribute = self.attribute
        new_dwn.alive = True
        new_dwn.file_size = attr_dwn["size"]
        new_dwn.progress = 0

        return {'FINISHED'}

class TexLibBrowser(Panel):
    bl_label = "Texlib Browser"
    bl_idname = "TEXLIB_PT_AmbientCG"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Ucupaint"
    

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        amb_br:TexLibProps = scene.ambient_browser
        sel_index = scene.material_index
        my_list = scene.material_items

        layout.prop(amb_br, "input_search")
        searching_dwn = amb_br.searching_download
       
        if searching_dwn.alive:
            layout.operator("texlib.cancel_search")
            prog = searching_dwn.progress
            if prog >= 0:
                if prog < 10:
                    layout.label(text="Searching...")
                else:
                    layout.label(text="Retrieving thumbnails..."+str(prog)+"%")
        # layout.operator("texlib.refresh_previews")
        # layout.operator("texlib.rem_material")
        # layout.prop(amb_br, "progress", slider=True, text="Download")
        # layout.template_icon_view(amb_br, "shaders_previews", show_labels=True,scale = 7, scale_popup = 5)
        # layout.label(text="download "+str(amb_br.persen))

        if len(my_list) > 0:
            layout.separator()
            layout.label(text="Textures:")
            layout.template_list("TEXLIB_UL_Material", "material_list", scene, "material_items", scene, "material_index")
            if sel_index < len(my_list):
                sel_mat = my_list[sel_index]
                mat_id:str = sel_mat.name
                layout.separator()
                layout.label(text="Preview:")
                selected_mat = layout.column(align=True)
                selected_mat.alignment = "CENTER"
                selected_mat.template_icon(icon_value=sel_mat.thumb, scale=5.0)
                selected_mat.label(text=mat_id)
                downloads = assets_lib[mat_id]["downloads"]

                layout.separator()
                layout.label(text="Attributes:")
                for d in downloads:
                    dwn = downloads[d]
                    row = layout.row()
                    ukuran = round(dwn["size"] / 1000000,2)

                  

                    check_exist:bool = False
                    lokasi = dwn["location"]
                    if os.path.exists(lokasi):
                        files = os.listdir(lokasi)
                        for f in files:
                            if mat_id in f:
                                check_exist = True
                                break
                    else:
                        check_exist = False

                    row.label(text=d)
                    row.label(text=str(ukuran)+ "MB")

                    thread_id = _get_thread_id(mat_id, d)
                    dwn_thread = _get_thread(thread_id)

                    if dwn_thread != None:
                        row.label(text=str(dwn_thread.progress)+"%")
                    else:
                        if check_exist:
                            row.label(text="Downloaded")
                        else:
                            op:TexLibDownload = row.operator("texlib.download", icon="IMPORT", text="")
                            op.attribute = d
                            op.id = sel_mat.name

        if len(amb_br.downloads):
            layout.separator()
            layout.label(text="Downloads:")
            layout.template_list("TEXLIB_UL_Downloads", "download_list", amb_br, "downloads", amb_br, "selected_download_item")


class MaterialItem(PropertyGroup): 
    name: StringProperty( name="Name", description="Material name", default="Untitled") 
    thumb: IntProperty( name="thumbnail", description="", default=0)

class TEXLIB_UL_Downloads(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        """Demo UIList."""

        # print("tipe ",self.layout_type)
        row = layout.row(align=True)
        # row.alignment = "CENTER"
        # Make sure your code supports all 3 layout types
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row.label(text=item.asset_id+" | "+item.asset_attribute+"="+str(item.progress))
            # layout.prop(amb_br, "progress", slider=True, text="Download")

       

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
    bl_label = "Cancel"
    
    
    def execute(self, context):
        thread_search = threads[THREAD_SEARCHING]
        thread_search.cancel = True
        ambr = context.scene.ambient_browser
        
        searching_dwn = ambr.searching_download
        searching_dwn.alive = False

        return{'FINISHED'}

def load_previews():
    # print(">>>>>>>>>>>>>>>>>>>>>>> INIT TexLIB")
    dir_name = _get_preview_dir()
    files = os.listdir(dir_name)
    
    previews_collection.clear()
    preview_items = {}
    for index, item in enumerate(files):
        file = dir_name + item
        my_id = item.split(".")[0]
        # print(">>item",item,"file",file)
        loaded = previews_collection.load(item, file, 'IMAGE', force_reload=True)
        preview_items[my_id] = (my_id, item, "", loaded.icon_id, index)

    previews_collection.preview_items.update(preview_items)

def monitor_downloads():
    
    interval = 0.1
    

    searching = False
    if THREAD_SEARCHING in threads:
        thread_search = threads[THREAD_SEARCHING]
        searching = True
    # else:
    #     return 1
    
    if not hasattr(bpy, 'context'):
        return 2
    scn = bpy.context.scene

    for area in bpy.context.screen.areas:
        if not area.type == 'VIEW_3D':
            continue
        area.tag_redraw()
    # if thread_search.progress == 100:
    #     thread_search.progress = -1
    
    amb = scn.ambient_browser
    downloads = amb.downloads

    if len(downloads) == 0 and not searching:
        # print("KOSONG")
        return 1 
    
    if searching:
        prog_search = thread_search.progress
        amb.searching_download.progress = prog_search
        if thread_search.progress >= 100:
            amb.searching_download.alive = False

        if not thread_search.is_alive():
            del threads[THREAD_SEARCHING]
    
    # print("downloadku", len(downloads))
    # for index, dwn in enumerate(downloads):
    #     print("cek aja",dwn.asset_id," | ",dwn.asset_attribute)
    
    to_remove = []
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

    
    return interval

def extract_file(my_file):
    dir_name = os.path.dirname(my_file)
    # new_folder = os.path.basename(my_file).split('.')[0]
    # dir_name = os.path.join(dir_name, new_folder)
    print("extract "+my_file+" to "+dir_name)

    with ZipFile(my_file, 'r') as zObject:
        zObject.extractall(path=dir_name)
        return dir_name
    
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
    print("download to ",directory)
    # print("asset",assets_lib)
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
            print("EXIST "+file_name)
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
                    dl += len(data)
                    f.write(data)                    
            except Exception as e:
                print('Error #2 while downloading', link, ':', e)
        prog = (index + 1) / item_count
        print("url = ",prog, ' | ',link,' | ', file_name)
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
        print("read ", content)
        return True
    return False

def retrieve_assets_info(keyword:str = '', page:int = 0, limit:int = 10):
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
    file_name_ori = os.path.join(dir_name, "lib-ori.json")

    response = requests.get(base_link, params=params, verify=False)
    if not response.status_code == 200:
        print("Can't download, Code: " + str(response.status_code))
        return None
    
    assets = response.json()["foundAssets"]
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

    file_ori = open(file_name_ori, 'w')
    file_ori.write(json.dumps({"foundAssets":assets}))
    file_ori.close()

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
    file_path = get_addon_filepath()
    retval = os.path.join(file_path, "library") + os.sep
    if not os.path.exists(retval):
        os.mkdir(retval)
    return retval

def _get_thread_id(asset_id:str, asset_attribute:str):
    return asset_id+"_"+asset_attribute

def _get_thread(id:str):
    if id in threads: 
        return threads[id]
    return None

classes = [DownloadThread, TexLibProps, TexLibBrowser, TexLibDownload, MaterialItem, TEXLIB_UL_Material
            ,TexLibCancelSearch, TEXLIB_UL_Downloads]

def register():
    for cl in classes:
        bpy.utils.register_class(cl)


    Scene.material_items = CollectionProperty(type= MaterialItem)
    Scene.material_index = IntProperty(default=0, name="Material index")
    Scene.material_attr_index = IntProperty(default=0, name="Attribute index")
    Scene.ambient_browser = PointerProperty(type= TexLibProps)

    global previews_collection
    previews_collection = bpy.utils.previews.new()
    previews_collection.preview_items = {}
    # load_previews()

    bpy.app.timers.register(monitor_downloads, first_interval=1, persistent=True)    

def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
    del bpy.types.Scene.ambient_browser
    del Scene.material_items
    del Scene.material_index
    del Scene.material_attr_index

    bpy.utils.previews.remove(previews_collection)

    if bpy.app.timers.is_registered(monitor_downloads):
        bpy.app.timers.unregister(monitor_downloads)

if __name__ == "__main__":
    register()