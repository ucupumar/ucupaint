import bpy, threading, os, json, zipfile, requests

from ..preferences import *

THREAD_SEARCHING = "thread_searching"
threads:dict[str, threading.Thread] = {} # progress:int,

def get_thread_id(asset_id:str, asset_attribute:str, texture_index:int = -1):
	if texture_index >= 0:
		return asset_id+"_"+asset_attribute+"_"+str(texture_index)
	else:
		return asset_id+"_"+asset_attribute
	
def get_thread(id:str) -> threading.Thread:
	if id in threads: 
		return threads[id]
	return None

def get_searching_thread() -> threading.Thread:
	if THREAD_SEARCHING in threads:
		return threads[THREAD_SEARCHING]
	return None

def set_searching_thread(thread:threading.Thread):
	threads[THREAD_SEARCHING] = thread

def download_stream(links:list[str], file_names:list[str], thread_id:str, 
							  timeout:int = 10,skipExisting:bool = False):
	thread = get_thread(thread_id)
	file_num = len(file_names)
	# percent_per_file = 100/file_num

	prog_total = 0
	for idx, file_name in enumerate(file_names):
		link = links[idx]
		prog = 0
		with open(file_name, "wb") as f:
			try:
				response = requests.get(link, stream=True, timeout = timeout)
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
					
					prog = int((100 * dl) / (total_length * file_num))
					# dl_threads[0].progress = prog
					thread.progress = prog_total + prog
					# print("proggg "+str(prog)+"%  "+str(dl)+"/"+str(total_length))
				# dl_threads.pop(0)
			except Exception as e:
				print('Error #2 while downloading', link, ':', e)
		prog_total += prog

def monitor_downloads():
		
	searching = False
	if THREAD_SEARCHING in threads:
		thread_search = threads[THREAD_SEARCHING]
		searching = True

	if not hasattr(bpy, 'context'):
		print("no context")
		return 2

	scn = bpy.context.scene

	from .properties import TexLibProps

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
			# if dwn.source_type == SourceType.SOURCE_POLYHAVEN_TEXTURE:
			# 	txt_idx = dwn.texture_index
			# 	thread_id = get_thread_id(dwn.asset_id, dwn.asset_attribute, txt_idx)
			# else:
			thread_id = get_thread_id(dwn.asset_id, dwn.asset_attribute)
			thread = get_thread(thread_id)
			if thread == None:
				print("thread id", thread_id, ">",dwn.asset_id,">", dwn.asset_attribute)
				if dwn.source_type == SourceType.SOURCE_AMBIENTCG:					
					extract_file(dwn.file_path)
					delete_zip(dwn.file_path)
					dir_file = os.path.dirname(dwn.file_path)
					convert_ambientcg_asset(dir_file, dwn.asset_id, dwn.asset_attribute)
				else:
					print("finishhh ", dwn.asset_id, " | ", dwn.asset_attribute)
					dir_file = os.path.dirname(dwn.file_path)
					# up 
					# dir_file = os.path.dirname(dir_file)
					mark_polyhaven_asset(dir_file, dwn.asset_id, dwn.asset_attribute)
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

from .data import AssetItem
def download_asset_previews(context, overwrite_existing:bool, search_results:dict[str, AssetItem], search_items):
	from .properties import get_preview_dir, load_per_material

	directory = get_preview_dir(context)

	if not os.path.exists(directory):
		os.mkdir(directory)
	
	thread_search = threads[THREAD_SEARCHING]
	
	progress_initial = thread_search.progress
	progress_max = 90
	span = progress_max - progress_initial
	item_count = len(search_results)

	for index,ast in enumerate(search_results.keys()):
		if thread_search.cancel:
			break

		link = search_results[ast].thumbnail
		file_name = bpy.path.basename(link)
		# remove parameters
		file_name = file_name.split("?")[0]
		file_name = os.path.join(directory, file_name)
		
		if not overwrite_existing and os.path.exists(file_name):
			continue
		
		with open(file_name, "wb") as f:
			try:
				print("download "+link+" to "+file_name)
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
		load_per_material(file_name, search_items[index])

		thread_search.progress = (int) (progress_initial + prog * span)

def download_previews(context, overwrite_existing:bool, material_items):
	from .properties import get_preview_dir, load_per_material
	from .properties import last_search

	directory = get_preview_dir(context)

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

def retrieve_assets_info(context, keyword:str = '', save_ori:bool = False, page:int = 0, limit:int = 20):
	from .properties import assets_lib, last_search
	from .properties import get_lib_dir, get_textures_dir

	base_link = "https://ambientCG.com/api/v2/full_json"
	params = {
		'type': 'Material',
		'include':'imageData,downloadData',
		'limit': str(limit),
		'offset': str(limit * page) 
	}

	if keyword != '':
		params['q'] = keyword
	
	dir_name = get_lib_dir(context)
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

	tex_directory = get_textures_dir(context)
	
	
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

from .data import AssetItem, SourceType
def retrieve_ambientcg(keyword:str = '', page:int = 0, limit:int = 20) -> dict[str, AssetItem]:
	base_link = "https://ambientCG.com/api/v2/full_json"
	params = {
		'type': 'Material',
		'include':'imageData,downloadData',
		'limit': str(limit),
		'offset': str(limit * page) 
	}

	if keyword != '':
		params['q'] = keyword

	response = requests.get(base_link, params=params, verify=False)
	if not response.status_code == 200:
		print("Can't download, Code: " + str(response.status_code))
		return None
	
	assets = response.json()["foundAssets"]

	print("Found ",len(assets), "textures")
	
	retval:dict[str, AssetItem] = {}
	
	for asst in assets:
		asset_id = asst["assetId"]
		thumbnail = asst["previewImage"]["256-PNG"]

		zip_assets = asst["downloadFolders"]["default"]["downloadFiletypeCategories"]["zip"]["downloads"]


		new_item = AssetItem()
		new_item.id = asset_id
		new_item.name = asset_id
		new_item.thumbnail = thumbnail
		new_item.source_type = SourceType.SOURCE_AMBIENTCG

		for k in zip_assets:
			attr = k["attribute"]
			new_item.add_attribute(attr, k["downloadLink"], k["fileName"], k["size"])
			retval[new_item.id] = new_item

	return retval

def retrieve_polyhaven_asset(id:str, asset_name:str, thumb_url:str)->AssetItem:
	base_link = "https://api.polyhaven.com/files/"+id
	response = requests.get(base_link, verify=False)
 	
	if not response.status_code == 200:
		print("Can't download, Code: " + str(response.status_code))
		return None
	
	retval = AssetItem()
	retval.source_type = SourceType.SOURCE_POLYHAVEN
	retval.id = id
	retval.name = asset_name
	retval.thumbnail = thumb_url

	obj = response.json()
	blend_obj = obj["blend"]
	for k in blend_obj.keys():
		blend_attr = blend_obj[k]["blend"]
		blnd_url = blend_attr["url"]
		includes = blend_attr["include"]
		file_name = blnd_url.split("/")[-1]

		new_attr = retval.add_attribute(k, blnd_url, file_name, blend_attr["size"])
		# print("k ", k, " content ", includes)
		for ic in includes.keys():
			inc_itm = includes[ic]
			url = inc_itm["url"]
			# get file name from url
			new_attr.add_texture(url, ic, inc_itm["size"])

	return retval
	
def retrieve_polyhaven(keyword:str = '', page:int = 0, limit:int = 20) -> dict[str, AssetItem]:

	base_link = "https://api.polyhaven.com/assets"
	params = {
		'type': 'textures',
		# 'limit': str(limit),
		# 'offset': str(limit * page) 
	}

	if keyword != '':
		params['c'] = keyword
	
	print("retrieve_polyhaven", base_link, params)
	response = requests.get(base_link, params=params, verify=False)
	if not response.status_code == 200:
		print("Can't download, Code: " + str(response.status_code))
		return None
	

	retval:dict[str, AssetItem] = {}
	
	obj_assets = response.json()
	# print("response ", json.dumps(obj_assets))

	for i, id in enumerate(obj_assets.keys()):
		# print("index ", i, "id ", id)
		if i >= limit:
			break

		it = obj_assets[id]
		# print("index ", i, "id ", id, "name ", it["name"], "thumb ", it["thumbnail_url"])
		new_item = retrieve_polyhaven_asset(id, it["name"], it["thumbnail_url"])
		retval[new_item.id] = new_item

	return retval

from .properties import get_textures_dir
def texture_exist(context, asset_id:str, attribute:str) -> bool:
	location = os.path.join(get_textures_dir(context), asset_id, attribute)
	if os.path.exists(location):
		files = os.listdir(location)
		for f in files:
			if asset_id in f:
				return True
	
	return False

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

def convert_ambientcg_asset(ambient_dir:str, id:str, attribute:str):
	import subprocess
	print("current directory: ", os.getcwd())
	print("data: ", ambient_dir, " | ", id)
	addon_dir = get_addon_dir()
	os.chdir(addon_dir)
	print("current directory next: ", os.getcwd())

	subprocess.call(
        [
            bpy.app.binary_path,
            "--background",
            "--factory-startup",
            "--python",
			os.path.join(addon_dir, "create_blend.py"),
            "--",
            "--target",
			ambient_dir,
			"--id",
			id,
			"--attribute",
			attribute
        ]
    )

def mark_polyhaven_asset(dir:str, id:str, attribute:str):
	import subprocess

	file_blend = ""
	for i in os.listdir(dir):
		# get blend file
		if i.endswith(".blend"):
			file_blend = os.path.join(dir, i)
			break
		print("file ", i)
	print("current directory: ", os.getcwd())
	print("data: ", dir, " | ", id, " | ", file_blend)
	addon_dir = get_addon_dir()
	os.chdir(addon_dir)
	print("current directory next: ", os.getcwd())

	if file_blend == "":
		print("failed")
		return
	
	subprocess.call(
        [
            bpy.app.binary_path,
            "--background",
            "--factory-startup",
			file_blend,
            "--python",
            os.path.join(addon_dir, "mark_blend.py"),
            "--",
			"--id",
			id,
			"--attribute",
			attribute
        ]
    )

def get_addon_dir() -> str:
	return os.path.dirname(os.path.realpath(__file__))


def register():
	bpy.app.timers.register(monitor_downloads, first_interval=1, persistent=True)    
	
def unregister():
	if bpy.app.timers.is_registered(monitor_downloads):
		bpy.app.timers.unregister(monitor_downloads)