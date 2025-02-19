import bpy, threading, os, json, pathlib

from bpy.props import StringProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty
from bpy.types import PropertyGroup, Context, Scene

from ..preferences import * 
from .. import lib

from .downloader import get_searching_thread, set_searching_thread, retrieve_ambientcg, retrieve_polyhaven, download_asset_previews
from .data import AssetItem

assets_library:dict[str, AssetItem] = {}
last_search = {}


def load_per_material(file_name:str, material_item):
	item = os.path.basename(file_name)

	my_id = item.split(".")[0]
	# print(">>item",item,"file",file_name, "my_id", my_id)
	loaded = previews_collection.load(item, file_name, 'IMAGE', force_reload=True)

	previews_collection.preview_items[my_id] = (my_id, item, "", loaded.icon_id, len(previews_collection.preview_items))
	material_item.thumb = loaded.icon_id

	
def cancel_searching(context):

	thread_search = get_searching_thread()
	if thread_search != None:
		thread_search.cancel = True
		
	texlib:TexLibProps = context.scene.texlib
	
	searching_dwn = texlib.searching_download
	searching_dwn.alive = False

def get_textures_dir(context) -> str:
	file_path = get_lib_dir(context)
	retval = os.path.join(file_path, "textures") + os.sep
	if not os.path.exists(retval):
		os.mkdir(retval)
	return retval

def get_preview_dir(context) -> str:
	file_path = get_lib_dir(context)
	retval = os.path.join(file_path, "previews") + os.sep
	if not os.path.exists(retval):
		os.mkdir(retval)
	return retval

def get_library_name():
	from ..common import get_addon_title

	return get_addon_title()+"Assets"
	
def get_asset_lib(context) -> bpy.types.UserAssetLibrary:
	for l in context.preferences.filepaths.asset_libraries:
		if l.name == get_library_name():
			return l
	return None

def get_os_config_dir() -> str:
	import platform

	# Get the operating system
	os_name = platform.system()

	print("build_platform", os_name)

	if os_name == 'Linux':
		default_dir =  os.path.expanduser("~/.config")
	elif os_name == 'Darwin':
		default_dir =  os.path.expanduser("~/Library/Application Support")
	else:
		default_dir =  os.path.expanduser("~\\AppData\\Roaming")

	return os.path.join(default_dir, get_addon_title(), "Assets")

def get_cat_asset_lib(context) -> str:
	asset_lib = get_asset_lib(context)
	if asset_lib == None:
		return None
	
	retval = os.path.join(asset_lib.path, "blender_assets.cats.txt")
	
	return retval

def get_lib_dir(context) -> str:
	# ypup:YPaintPreferences = get_user_preferences()
	asset_lib = get_asset_lib(context)
	if asset_lib == None:
		return None
	
	retval = asset_lib.path

	if not os.path.exists(retval):
		os.mkdir(retval)
	return retval

def read_asset_info(context) -> bool:
	dir_name = get_lib_dir(context)
	if dir_name == None:
		return False
	
	file_name = os.path.join(dir_name, "assets.json")

	if os.path.exists(file_name):
		file = open(file_name, 'r')
		content = file.read()
		jsn = json.loads(content)
		# new_dict =  {k: v.to_dict() for k, v in jsn}
		for key in jsn:
			assets_library[key] = AssetItem.from_dict(jsn[key])
			# if assets_library[key].source_type == "polyhaven":
			# 	print("\n>>>>>>",jsn[key])
		# assets_library.update(new_dict)
		file.close()
		return True
	return False

def retrieve_asset_library(context:Context):
	asset_path = get_lib_dir(context)
	if asset_path == None:
		return None

	scene = context.scene
	txlib:TexLibProps = scene.texlib

	print("asset_lib=", asset_path)
	txlib.library_items.clear()

	library_path = pathlib.Path(asset_path)
	blend_files = [fp for fp in library_path.glob("**/*.blend") if fp.is_file()]
	for blend_file in blend_files:
		with bpy.data.libraries.load(str(blend_file), assets_only=True) as (data_from, data_to):
			for mat in data_from.materials:
				new_item:MaterialItem = txlib.library_items.add()
				new_item.name = mat
				new_item.source_type = ""

				nama = mat
				# split string and remove last index
				split_name = nama.split("_")[:-1]
				# combine array string into one string
				new_id = "_".join(split_name)
				new_item.asset_id = new_id

def searching_material(context:Context, keyword:str, search_ambientcg:bool = True, search_polyhaven:bool = True):

	scene = context.scene
	txlib:TexLibProps = scene.texlib

	thread_search = get_searching_thread()

	if not len(assets_library):
		read_asset_info(context)

	thread_search.progress = 10

	search_results:dict[str, AssetItem] = {}
	if search_ambientcg:
		search_results = retrieve_ambientcg(keyword)
	thread_search.progress = 30

	if search_polyhaven:
		list_polyhaven = retrieve_polyhaven(keyword)
		search_results.update(list_polyhaven)
	thread_search.progress = 60

	assets_library.update(search_results)

	save_library_to_file(context, search_results, "last-search.json")
	thread_search.progress = 65

	save_library_to_file(context, assets_library, "assets.json")

	thread_search.progress = 70

	txlib.search_items.clear()
	for key in search_results:
		new_item:MaterialItem = txlib.search_items.add()
		asst_item = search_results[key]
		new_item.name = asst_item.name
		new_item.asset_id = asst_item.id
		new_item.source_type = asst_item.source_type

	download_asset_previews(context, False, search_results, txlib.search_items)

	read_asset_info(context)
	
	load_previews(context)
	thread_search.progress = 100


def save_library_to_file(context, list:dict[str, AssetItem], file_name:str):
	dir_name = get_lib_dir(context)
	file_name = os.path.join(dir_name, file_name)

	file = open(file_name, 'w')

	to_write = {}
	for key in list:
		to_write[key] = list[key].to_dict()

	file.write(json.dumps(to_write))
	file.close()
	print("stored to ", file_name)


def load_previews(context):
	print(">>>>>>>>>>>>>>>>>>>>>>> INIT TexLIB")
	dir_name = get_preview_dir(context)
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

	# if self.input_last == self.input_search:
	# 	print("no search:"+self.input_search)
	# 	return
	
	self.input_last = self.input_search

	txlib:TexLibProps = context.scene.texlib
	txlib.material_items.clear()
	txlib.search_items.clear()

	if self.input_search == '':
		last_search.clear()
		if get_searching_thread() != None:
			cancel_searching(context)
		return

	# cancel previous search
	if get_searching_thread() != None:
		cancel_searching(context)

	thread_search = threading.Thread(target=searching_material, args=(context, self.input_search, self.check_ambiencg, self.check_polyhaven))
	thread_search.progress = 0
	thread_search.cancel = False
	set_searching_thread(thread_search)

	thread_search.start()

	self.searching_download.progress = 0
	self.searching_download.alive = True

def change_mode_asset(self, context):

	retrieve_asset_library(context)


class TextureItem (PropertyGroup):
	texture_id: StringProperty(name="Texture ID")
	location: StringProperty(name="Location", subtype="FILE_PATH")
	thumbnail: StringProperty(name="Thumbnail", subtype="FILE_PATH") 
	blend_file: StringProperty(name="Blend File", subtype="FILE_PATH")

class MaterialItem(PropertyGroup): 
	asset_id: StringProperty(name="Asset ID")
	name: StringProperty( name="Name", description="Material name", default="Untitled") 
	source_type: StringProperty( name="Source Type", description="Source type", default="")
	# thumb: IntProperty( name="thumbnail", description="", default=0)

class DownloadQueue(PropertyGroup):
	asset_id : StringProperty()
	asset_attribute: StringProperty()
	asset_cat_id: StringProperty()
	tags: StringProperty()
	texture_index: IntProperty(default=-1)
	file_path : StringProperty()
	source_type: StringProperty()
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
	check_local:BoolProperty(name="Local", default=True)
	check_ambiencg:BoolProperty(name="AmbientCG", default=True)
	check_polyhaven:BoolProperty(name="Polyhaven", default=True)
	mode_asset:EnumProperty(
		items =  (('SEARCH', 'Search', ''), ('LIBRARY', 'Library', '')),
		name = 'Location',
		default = 'SEARCH',
		# description = 'Location of the PBR Texture.\n'
		# 	'  Local: the assets that you have already downloaded.\n'
		# 	'  Online: available for download on AmbientCG.com.\n',
		update=change_mode_asset
	)

	input_last:StringProperty()
	material_items:CollectionProperty(type= MaterialItem)
	material_index:IntProperty(default=0, name="Material index")
	downloaded_material_items:CollectionProperty(type= MaterialItem)
	downloaded_material_index:IntProperty(default=0, name="Material index")


	search_items:CollectionProperty(type= MaterialItem)
	search_index:IntProperty(default=0, name="Search index")

	library_items:CollectionProperty(type= MaterialItem)
	library_index:IntProperty(default=0, name="Search index")

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

	if read_asset_info(bpy.context):
		load_previews(bpy.context)
	
	# retrieve_asset_library(bpy.context)

	# from .data import SourceType
	# for idx, lb in enumerate(assets_library):
	# 	item = assets_library[lb]
	# 	if item.source_type == SourceType.SOURCE_POLYHAVEN:
	# 		print(item.id, item.name, item.thumbnail, item.source_type)
	# 		for at in item.attributes:
	# 			print(">>", at)
	# 			for tx in item.attributes[at].textures:
	# 				print(">>>",tx.file_name, tx.size)


def unregister():
	for cl in classes:
		bpy.utils.unregister_class(cl)

	del bpy.types.Scene.texlib
	bpy.utils.previews.remove(previews_collection)