import typing
from bpy.types import AnyType, Context, UILayout
from .common import * 
from .lib import *

import bpy, threading, os, requests, json
from bpy.props import *
from bpy.types import PropertyGroup, Panel, Operator, UIList, Scene


# thread_search:threading.Thread # progress:int
addon_folder = os.path.dirname(__file__)
# global previews_collection
# preview_items = []
assets_lib = {}
last_search = {}

# def preview_enums(self, context):
#     return previews_collection.preview_items

def update_input_search(self, context):
    if self.input_last == self.input_search:
        print("no search:"+self.input_search)
        return
    
    self.input_last = self.input_search

    context.scene.material_items.clear()

    if self.input_search == '':
        last_search.clear()
        return

    global thread_search
    thread_search = threading.Thread(target=searching_material, args=(self.input_search,context))
    thread_search.progress = 0
    thread_search.stop = False
    thread_search.start()

    self.progress = 0
    
def searching_material(keyword:str, context:Context):
    scene = context.scene

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

class TexLibProps(bpy.types.PropertyGroup):
    page: IntProperty(name="page", default= 0)
    input_search:StringProperty(name="Search", update=update_input_search)
    input_last:StringProperty()
    progress : IntProperty(
        default = -1,
        min = -1,
        max = 100,
        description = 'Progress of the download',
        subtype = 'PERCENTAGE'
    )


class TexLibDownload(Operator):
    bl_label = "texlib Download"
    bl_idname = "texlib.download"

    attribute:bpy.props.StringProperty()
    id:bpy.props.StringProperty()
    
    def execute(self, context):
        # scene = context.scene
        # sel_index = scene.material_index
        # my_list = scene.material_items
        # if sel_index < len(my_list):

            # scene = context.scene
            # amb_br = scene.ambient_browser
            # content = amb_br.input_search

            # thread = threading.Thread(target=download_stream, args=("https://acg-download.struffelproductions.com/file/ambientCG-Web/download/Ground068_c5MREyAu/Ground068_1K-JPG.zip", 30))
            # thread.progress = 0.0
            # dl_threads.append(thread)

            # thread.start()
        lib = assets_lib[self.id]
        print("setar =",self.attribute, "selected = "+self.id, "lib =", lib["downloads"][self.attribute]["link"])
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
        amb_br = scene.ambient_browser
        sel_index = scene.material_index
        my_list = scene.material_items

        layout.prop(amb_br, "input_search")

        if amb_br.progress >= 0:
            layout.label(text="Searching..."+str(amb_br.progress)+"%")
            layout.operator("texlib.cancel_search")
        # layout.operator("texlib.refresh_previews")
        # layout.operator("texlib.rem_material")
        # layout.prop(amb_br, "progress", slider=True, text="Download")
        # layout.template_icon_view(amb_br, "shaders_previews", show_labels=True,scale = 7, scale_popup = 5)
        # layout.label(text="download "+str(amb_br.persen))

        if len(my_list) > 0:
            layout.template_list("TEXLIB_UL_Material", "material_list", scene, "material_items", scene, "material_index")
        # print("index ", sel_index, "my list", len(my_list))
            if sel_index < len(my_list):
                sel_mat = my_list[sel_index]
            
                layout.separator()
                selected_mat = layout.column(align=True)
                selected_mat.alignment = "CENTER"
                selected_mat.template_icon(icon_value=sel_mat.thumb, scale=5.0)
                selected_mat.label(text=sel_mat.name)
                downloads = assets_lib[sel_mat.name]["downloads"]

                for d in downloads:
                    op = layout.operator("texlib.download", text=d)
                    op.attribute = d
                    op.id = sel_mat.name

class MaterialItem(PropertyGroup): 
    name: StringProperty( name="Name", description="Material name", default="Untitled") 
    thumb: IntProperty( name="thumbnail", description="", default=0)


class TEXLIB_UL_Material(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        """Demo UIList."""

#   index = scene.material_index
        scene = context.scene
        my_list = scene.material_items


        # print("tipe ",self.layout_type)
        row = layout.row(align=True)
        # row.alignment = "CENTER"
        # Make sure your code supports all 3 layout types
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
        thread_search.stop = True

        return{'FINISHED'}

    
class TexLibMaterialNewItem(Operator):
    """Add a new item to the list."""

    bl_idname = "texlib.new_material"
    bl_label = "Add material"
    @classmethod
    def poll(cls, context: Context):
        return context.scene.ambient_browser.input_search
    
    def execute(self, context):
        scene = context.scene
        amb_br = scene.ambient_browser
        content = amb_br.input_search

        new_item = context.scene.material_items.add()

        print("add content "+content)
        new_item.name = content

        amb_br.input_search = ""

        return{'FINISHED'}

class TexLibMaterialDelItem(Operator):
    """remove item to the list."""

    bl_idname = "texlib.rem_material"
    bl_label = "Remove material"

    @classmethod
    def poll(cls, context: Context):
        return context.scene.material_items
    
    def execute(self, context):
        scene = context.scene
        index = scene.material_index
        my_list = scene.material_items

        my_list.remove(index)

        context.scene.material_index = 0

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
        print(">>item",item,"file",file)
        loaded = previews_collection.load(item, file, 'IMAGE', force_reload=True)
        preview_items[my_id] = (my_id, item, "", loaded.icon_id, index)

    previews_collection.preview_items.update(preview_items)

def monitor_downloads():
    
    interval = 0.1
   
    
    try:
        thread_search
    except:
        return 1

    if not thread_search.is_alive() and thread_search.progress < 0:
        return 1
    
    if not hasattr(bpy, 'context'):
        return 2
    scn = bpy.context.scene

    for area in bpy.context.screen.areas:
        if not area.type == 'VIEW_3D':
            continue
        area.tag_redraw()
        # for sp in area.spaces:
        #     print("redraw ",sp.type)
        # if area.spaces[0].tree_type == "ShaderNodeTree":
        #     update_progress = True
        #     area.tag_redraw()


    if thread_search.progress == 100:
        thread_search.progress = -1
    
    amb = scn.ambient_browser
    amb.progress = thread_search.progress


        
    # if thread_search.is_alive():
    #     thread_search.progress 
    
    return interval

def download_stream(link, timeout, skipExisting = False):
    directory = bpy.path.abspath("//textures")

    file_name = bpy.path.basename(link)
    file_name = os.path.join(directory, file_name)
    print("url = "+link)
    print("base name = "+file_name)
    
    # if not skipExisting and os.path.exists(file_name):
    #     print("EXIST "+file_name)
    #     return file_name
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

    progress_initial = thread_search.progress
    progress_max = 90
    span = progress_max - progress_initial
    item_count = len(last_search)

    for index,ast in enumerate(last_search):
        if thread_search.stop:
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

    response = requests.get(base_link, params=params)
    if not response.status_code == 200:
        print("Can't download, Code: " + str(response.status_code))
        return None
    
    assets = response.json()["foundAssets"]
    file = open(file_name, 'w')

    # assets_lib = {}
    last_search.clear()
    for asst in assets:
        asset_obj = {}
        asset_obj["id"] = asst["assetId"]
        asset_obj["preview"] = asst["previewImage"]["256-PNG"]

        zip_assets = asst["downloadFolders"]["default"]["downloadFiletypeCategories"]["zip"]["downloads"]
        downloads = {}
        for k in zip_assets:
            downloads[k["attribute"]] = {
                "link" : k["downloadLink"],
                "fileName" : k["fileName"]
            }
        asset_obj["downloads"] = downloads
        assets_lib[asst["assetId"]] = asset_obj
        last_search[asst["assetId"]] = asset_obj

    file.write(json.dumps(assets_lib))
    file.close()
    print("stored to ", file_name)
    # print("content to ", str(assets_lib))

    file_ori = open(file_name_ori, 'w')
    file_ori.write(json.dumps({"foundAssets":assets}))
    file_ori.close()

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

classes = [TexLibProps, TexLibBrowser, TexLibDownload, MaterialItem, TEXLIB_UL_Material
           ,TexLibMaterialNewItem, TexLibMaterialDelItem, TexLibCancelSearch]

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