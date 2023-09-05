import typing
from bpy.types import AnyType, Context, UILayout
from .common import * 
from .lib import *

import bpy, threading, os, requests, json
from bpy.props import *
from bpy.types import PropertyGroup, Panel, Operator, UIList, Scene


dl_threads = []
addon_folder = os.path.dirname(__file__)
# global previews_collection
# preview_items = []
assets_lib = {}

def preview_enums(self, context):
    return previews_collection.preview_items
    

class TexLibProps(bpy.types.PropertyGroup):
    page: IntProperty(name="page", default= 0)
    input_search:StringProperty(name="Search")
    persen:StringProperty()
    progress : IntProperty(
        default = 0,
        min = 0,
        max = 100,
        description = 'Progress of the download',
        subtype = 'PERCENTAGE'
    )
    shaders_previews : EnumProperty(
        name = 'PBR Shader',
        items = preview_enums,
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
        layout.operator("texlib.search_material")
        layout.operator("texlib.refresh_previews")
        # layout.operator("texlib.rem_material")
        # layout.prop(amb_br, "progress", slider=True, text="Download")
        # layout.template_icon_view(amb_br, "shaders_previews", show_labels=True,scale = 7, scale_popup = 5)
        # layout.label(text="download "+str(amb_br.persen))
        layout.template_list("TexLibMaterialUIList", "material_list", scene, "material_items", scene, "material_index")
        
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


class TexLibMaterialUIList(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        """Demo UIList."""

        # We could write some code to decide which icon to use here...
        thumb = previews_collection.preview_items[index % 4][3]

        # print("tipe ",self.layout_type)
        row = layout.row(align=True)
        # row.alignment = "CENTER"
        # Make sure your code supports all 3 layout types
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row.template_icon(icon_value = thumb, scale = 1.0)
            row.label(text=item.name)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon_value = thumb)

class TexLibRefreshItems(Operator):
    bl_idname = "texlib.refresh_previews"
    bl_label = "Refresh previews"
    
    
    def execute(self, context):
        scene = context.scene
        amb_br = scene.ambient_browser
        context.scene.material_items.clear()
        if not read_asset_info():
            retrieve_assets_info(0, 10)
        
        # new_t = threading.Thread(target=download_previews, args=(False      ,))
        # new_t.start()
        download_previews(False)
        load_previews()
        for index, item in enumerate(previews_collection.preview_items):
            new_item = context.scene.material_items.add()
            new_item.name = item[0]
            new_item.thumb = item[3]
       
        return{'FINISHED'}
    
class TexLibSearchMaterial(Operator):
    bl_idname = "texlib.search_material"
    bl_label = "Search Materials"
    
    
    def execute(self, context):
        scene = context.scene
        amb_br = scene.ambient_browser
        retrieve_assets_info(0, 10)
       
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
    
classes = [TexLibProps, TexLibBrowser, TexLibDownload, MaterialItem, TexLibMaterialUIList
           ,TexLibMaterialNewItem, TexLibMaterialDelItem, TexLibRefreshItems, TexLibSearchMaterial]

def register():
    for cl in classes:
        bpy.utils.register_class(cl)

    Scene.material_items = CollectionProperty(type= MaterialItem)
    Scene.material_index = IntProperty(default=0, name="Material index")
    Scene.material_attr_index = IntProperty(default=0, name="Attribute index")
    Scene.ambient_browser = PointerProperty(type= TexLibProps)

    global previews_collection
    previews_collection = bpy.utils.previews.new()

    # load_previews()

    # bpy.app.timers.register(monitor_downloads, first_interval=1, persistent=True)    

def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
    del bpy.types.Scene.ambient_browser
    del Scene.material_items
    del Scene.material_index
    del Scene.material_attr_index

    bpy.utils.previews.remove(previews_collection)

    # if bpy.app.timers.is_registered(monitor_downloads):
    #     bpy.app.timers.unregister(monitor_downloads)

def load_previews():
    print(">>>>>>>>>>>>>>>>>>>>>>> INIT TexLIB")

    # mat_items = ("Asphalt001.png", "Asphalt002.png", "Candy001.png", "Candy002.png")
    

    dir_name = _get_preview_dir()
    print("fp = "+dir_name)
    files = os.listdir(dir_name)
    
    previews_collection.clear()
    preview_items = []
    # for index, item in enumerate(mat_items):
    for index, item in enumerate(files):
        file = dir_name + item
        print(">> fp = ", file)

        loaded = previews_collection.load(item, file, 'IMAGE', force_reload=True)

        
        preview_items.append((item.split(".")[0], item, "", loaded.icon_id, index))

        # Scene.ambient_browser.shaders_previews.
    previews_collection.preview_items = preview_items

def monitor_downloads():
    
    interval = 0.5 # execute every x seconds, 2 times a second in our case
    # update_progress = False
    if not hasattr(bpy, 'context'):
        return 2
    
    scn = bpy.context.scene

    for area in bpy.context.screen.areas:
        # print("area type "+area.type)

        if not area.type == 'VIEW_3D':
            continue
        area.tag_redraw()
        for sp in area.spaces:
            print("redraw ",sp.type)
        # if area.spaces[0].tree_type == "ShaderNodeTree":
        #     update_progress = True
        #     area.tag_redraw()

    amb = scn.ambient_browser
    amb.progress += 1
    if amb.progress >= 100:
        amb.progress = 0
    amb.persen = str(amb.progress) + "%"
    # for dl_thread in dl_threads:
    #     if dl_thread and dl_thread.is_alive():
    #         progg = int(dl_thread.progress)
    #         print("cek cek",progg)
    #         amb.progress = progg
    #         amb.persen = str(progg) + "%"
    # print("monitor download "+str(interval))
    
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
                dl_threads[0].progress = prog
                
                # print("proggg "+str(prog)+"%  "+str(dl)+"/"+str(total_length))
            dl_threads.pop(0)
        except Exception as e:
            print('Error #2 while downloading', link, ':', e)

def download_previews(overwrite_existing:bool):
    directory = _get_preview_dir()
    print("download to ",directory)
    print("asset",assets_lib)
    for ast in assets_lib:
        link = assets_lib[ast]["preview"]
        file_name = bpy.path.basename(link)
        file_name = os.path.join(directory, file_name)
        
        if not overwrite_existing and os.path.exists(file_name):
            print("EXIST "+file_name)
            continue
        print("url = ",link, file_name)
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

def read_asset_info() -> bool:
    dir_name = get_addon_filepath()
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

def retrieve_assets_info(page:int, limit:int):
    base_link = "https://ambientCG.com/api/v2/full_json"
    params = {
        'type': 'Material',
        'include':'imageData,downloadData',
        'limit': str(limit),
        'offset': str(limit * page) 
    }
    


    dir_name = get_addon_filepath()
    file_name = os.path.join(dir_name, "lib.json")
    file_name_ori = os.path.join(dir_name, "lib-ori.json")


    

    response = requests.get(base_link, params=params)
    if not response.status_code == 200:
        print("Can't download, Code: " + str(response.status_code))
        return None
    
    assets = response.json()["foundAssets"]
    file = open(file_name, 'w')

    assets_lib = {}
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

    file.write(json.dumps(assets_lib))
    file.close()
    print("stored to ", file_name)
    # print("content to ", str(assets_lib))

    file_ori = open(file_name_ori, 'w')
    file_ori.write(json.dumps({"foundAssets":assets}))
    file_ori.close()

def _get_preview_dir():
    file_path = get_addon_filepath()
    return os.path.join(file_path, "previews") + os.sep

if __name__ == "__main__":
    register()