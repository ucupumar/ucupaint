import bpy, threading, os,  json

from bpy.props import StringProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty
from bpy.types import PropertyGroup, Context, Scene

from ..preferences import * 
from .. import lib

from .downloader import get_searching_thread, set_searching_thread, retrieve_ambientcg, retrieve_assets_info, download_previews, retrieve_polyhaven
from .data import AssetItem

assets_lib = {} 

assets_library:dict[str, AssetItem] = {}
last_search = {}

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

    
def cancel_searching(context):

    thread_search = get_searching_thread()
    thread_search.cancel = True
    texlib = context.scene.texlib
    
    searching_dwn = texlib.searching_download
    searching_dwn.alive = False

def update_check_all(self, context):
    self.check_local = self.check_all
    self.check_ambiencg = self.check_all
    self.check_polyhaven = self.check_all

def get_textures_dir() -> str:
	file_path = get_lib_dir()
	retval = os.path.join(file_path, "textures") + os.sep
	if not os.path.exists(retval):
		os.mkdir(retval)
	return retval

def get_preview_dir() -> str:
	file_path = get_lib_dir()
	retval = os.path.join(file_path, "previews") + os.sep
	if not os.path.exists(retval):
		os.mkdir(retval)
	return retval

def get_lib_dir() -> str:
	ypup:YPaintPreferences = get_user_preferences()
	retval = ypup.library_location
	if not os.path.exists(retval):
		os.mkdir(retval)
	return retval

def read_asset_info() -> bool:
	dir_name = get_lib_dir()
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

def searching_material(keyword:str, context:Context):

    scene = context.scene
    txlib:TexLibProps = scene.texlib

    thread_search = get_searching_thread()

    if not len(assets_lib):
        read_asset_info()

    list_ambient = retrieve_ambientcg(keyword)
    assets_library.update(list_ambient)
    list_polyhaven = retrieve_polyhaven(keyword)
    assets_library.update(list_polyhaven)


    save_library_to_file()

    retrieve_assets_info(keyword)
    thread_search.progress = 10
    load_material_items(txlib.material_items, last_search)

    download_previews(False, txlib.material_items)
    thread_search.progress = 90
    load_previews()
    thread_search.progress = 95

    load_material_items(txlib.material_items, last_search)
    thread_search.progress = 100

def save_library_to_file():
    dir_name = get_lib_dir()
    file_name = os.path.join(dir_name, "assets.json")

    file = open(file_name, 'w')

    to_write = {}
    for key in assets_library:
        to_write[key] = assets_library[key].to_dict()

    file.write(json.dumps(to_write))
    file.close()
    print("stored to ", file_name)


def load_previews():
    print(">>>>>>>>>>>>>>>>>>>>>>> INIT TexLIB")
    dir_name = get_preview_dir()
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
    if get_searching_thread() != None:
        cancel_searching(context)

    thread_search = threading.Thread(target=searching_material, args=(self.input_search,context))
    thread_search.progress = 0
    thread_search.cancel = False
    set_searching_thread(thread_search)

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
    # thumb: IntProperty( name="thumbnail", description="", default=0)

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



def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)

    del bpy.types.Scene.texlib
    bpy.utils.previews.remove(previews_collection)