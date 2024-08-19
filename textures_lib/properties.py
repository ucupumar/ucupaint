import bpy, threading, os, json, zipfile, requests

from bpy.props import StringProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty
from bpy.types import PropertyGroup, Context, Scene

from ..preferences import * 
from .. import lib


THREAD_SEARCHING = "thread_searching"
# thread_search:threading.Thread # progress:int
# previews_collection:bpy.utils.previews
# preview_items = []
assets_lib = {}
last_search = {}

threads = {} # progress:int,


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



def retrieve_assets_info(keyword:str = '', save_ori:bool = False, page:int = 0, limit:int = 20):
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
    
def cancel_searching(context):
    thread_search = threads[THREAD_SEARCHING]
    thread_search.cancel = True
    texlib = context.scene.texlib
    
    searching_dwn = texlib.searching_download
    searching_dwn.alive = False

def update_check_all(self, context):
    self.check_local = self.check_all
    self.check_ambiencg = self.check_all
    self.check_polyhaven = self.check_all

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
    print(">>>>>>>>>>>>>>>>>>>>>>> INIT TexLIB")
    dir_name = _get_preview_dir()
    files = os.listdir(dir_name)
    
    previews_collection.clear()
    preview_items = {}
    for index, item in enumerate(files):
        file = dir_name + item
        my_id = item.split(".")[0]
        sizefile = os.path.getsize(file)
        if sizefile == 0: # detect corrupt image
            os.remove(file)
            continue
        loaded = previews_collection.load(item, file, 'IMAGE', force_reload=True)
        # print(">>item",item,"file",file,"size", sizefile, "id", loaded.icon_id)

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

    # if self.mode_asset == "ONLINE":
    #     pass
    # else:
    #     textures_dir = _get_textures_dir()
    #     tex_lis = os.listdir(textures_dir)

    #     _offline_files = {}
    #     for tx in tex_lis:
    #         tx_dir = os.path.join(textures_dir, tx)
    #         attr_lis = os.listdir(tx_dir)

    #         for att in attr_lis:
    #             attr_dir = os.path.join(tx_dir, att)
    #             if _texture_exist(tx, attr_dir):
    #                 _offline_files[tx] = assets_lib[tx] 
    #                 break       

    #     load_material_items(self.downloaded_material_items, _offline_files)

class TextureItem (PropertyGroup):
	texture_id: StringProperty(name="Texture ID")
	location: StringProperty(name="Location", subtype="FILE_PATH")
	thumbnail: StringProperty(name="Thumbnail", subtype="FILE_PATH") 
	blend_file: StringProperty(name="Blend File", subtype="FILE_PATH")

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

class TexLibProps(PropertyGroup):
    page: IntProperty(name="page", default= 0)
    input_search:StringProperty(name="Search", update=update_input_search)
    check_all:BoolProperty(name="Check All", default=True, update=update_check_all)
    check_local:BoolProperty(name="Local", default=True)
    check_ambiencg:BoolProperty(name="AmbientCG", default=True)
    check_polyhaven:BoolProperty(name="Polyhaven", default=True)

    input_last:StringProperty()
    material_items:CollectionProperty(type= MaterialItem)
    material_index:IntProperty(default=0, name="Material index")
    downloaded_material_items:CollectionProperty(type= MaterialItem)
    downloaded_material_index:IntProperty(default=0, name="Material index")

    # mode_asset:EnumProperty(
    #         items =  (('ONLINE', 'Online', ''), ('DOWNLOADED', 'Downloaded', '')),
    #         name = 'Location',
    #         default = 'ONLINE',
    #         description = 'Location of the PBR Texture.\n'
    #             '  Local: the assets that you have already downloaded.\n'
    #             '  Online: available for download on AmbientCG.com.\n',
    #         update=change_mode_asset
    #     )

    downloads:CollectionProperty(type=DownloadQueue)
    searching_download:PointerProperty(type=DownloadQueue)
    selected_download_item:IntProperty(default=0)

classes = [
    TextureItem, MaterialItem, DownloadQueue, TexLibProps
]

def register():
    for cl in classes:
        bpy.utils.register_class(cl)

    Scene.texlib = PointerProperty(type= TexLibProps)

    global previews_collection
    previews_collection = bpy.utils.previews.new()
    previews_collection.preview_items = {}

    if read_asset_info():
        load_previews()

    bpy.app.timers.register(monitor_downloads, first_interval=1, persistent=True)    


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)

    del bpy.types.Scene.texlib

    bpy.utils.previews.remove(previews_collection)

    if bpy.app.timers.is_registered(monitor_downloads):
        bpy.app.timers.unregister(monitor_downloads)