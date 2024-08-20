import bpy, threading, os, json, zipfile, requests

from ..preferences import *

THREAD_SEARCHING = "thread_searching"
threads = {} # progress:int,

def get_thread_id(asset_id:str, asset_attribute:str):
	return asset_id+"_"+asset_attribute

def get_thread(id:str):
	if id in threads: 
		return threads[id]
	return None

def get_searching_thread():
	if THREAD_SEARCHING in threads:
		return threads[THREAD_SEARCHING]
	return None

def set_searching_thread(thread:threading.Thread):
	threads[THREAD_SEARCHING] = thread
	
def download_stream(link:str, file_name:str, thread_id:str,
					timeout:int = 10,skipExisting:bool = False):
	# print("url = ",link, "filename", file_name)

	thread = get_thread(thread_id)
	
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
			
			thread_id = get_thread_id(dwn.asset_id, dwn.asset_attribute)
			thread = get_thread(thread_id)
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

def download_previews(overwrite_existing:bool, material_items):
	from .properties import get_preview_dir, load_per_material
	from .properties import last_search

	directory = get_preview_dir()

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
	
	dir_name = get_lib_dir()
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

	tex_directory = get_textures_dir()
	
	
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

def texture_exist(asset_id:str, location:str) -> bool:
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


def register():
	bpy.app.timers.register(monitor_downloads, first_interval=1, persistent=True)    
	
def unregister():
	if bpy.app.timers.is_registered(monitor_downloads):
		bpy.app.timers.unregister(monitor_downloads)