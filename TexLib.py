import typing
from bpy.types import AnyType, Context, UILayout
from .common import * 
from .lib import *

import bpy, threading, os, requests
from bpy.props import *
from bpy.types import PropertyGroup, Panel, Operator, UIList, Scene


dl_threads = []
addon_folder = os.path.dirname(__file__)
global previews_collection
preview_items = []

def preview_enums(self, context):
    return preview_items
    

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

class TexLibDownloadOp(Operator):
    bl_label = "Ambient Op"
    bl_idname = "texlib.op"
    
    
    def execute(self, context):
        scene = context.scene
        amb_br = scene.ambient_browser
        content = amb_br.input_search

        thread = threading.Thread(target=download_stream, args=("https://acg-download.struffelproductions.com/file/ambientCG-Web/download/Ground068_c5MREyAu/Ground068_1K-JPG.zip", 30))
        thread.progress = 0.0
        dl_threads.append(thread)

        thread.start()
        print("setar = "+content)
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
        layout.operator("texlib.new_material")
        layout.operator("texlib.refresh_material")
        layout.operator("texlib.rem_material")
        # layout.prop(amb_br, "progress", slider=True, text="Download")
        # layout.template_icon_view(amb_br, "shaders_previews", show_labels=True,scale = 7, scale_popup = 5)
        # layout.label(text="download "+str(amb_br.persen))
        layout.template_list("TexLibMaterialUIList", "material_list", scene, "material_items", scene, "material_index")
        
        sel_mat = my_list[sel_index]
        layout.separator()
        prev = layout.column(align=True)
        prev.alignment = "CENTER"
        prev.template_icon(icon_value=sel_mat.thumb, scale=5.0)
        prev.label(text=sel_mat.name)

class MaterialItem(PropertyGroup): 
    name: StringProperty( name="Name", description="Material name", default="Untitled") 
    thumb: IntProperty( name="thumbnail", description="", default=0)


class TexLibMaterialUIList(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        """Demo UIList."""

        # We could write some code to decide which icon to use here...
        thumb = preview_items[index % 4][3]

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
    """Add a new item to the list."""

    bl_idname = "texlib.refresh_material"
    bl_label = "Refresh material"
    
    
    def execute(self, context):
        scene = context.scene
        amb_br = scene.ambient_browser
        context.scene.material_items.clear()
        for index, item in enumerate(preview_items):
            new_item = context.scene.material_items.add()
            new_item.name = item[0]
            new_item.thumb = item[3]

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
    
classes = [TexLibProps, TexLibBrowser, TexLibDownloadOp, MaterialItem, TexLibMaterialUIList
           ,TexLibMaterialNewItem, TexLibMaterialDelItem, TexLibRefreshItems]

def register():
    for cl in classes:
        bpy.utils.register_class(cl)

    Scene.material_items = CollectionProperty(type=MaterialItem)
    Scene.material_index = IntProperty(default=0, name="Material index")
    Scene.ambient_browser = PointerProperty(type= TexLibProps)

    init_test_thumbnails()

    # bpy.app.timers.register(monitor_downloads, first_interval=1, persistent=True)    

def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
    del bpy.types.Scene.ambient_browser
    del Scene.material_items
    del Scene.material_index

    # if bpy.app.timers.is_registered(monitor_downloads):
    #     bpy.app.timers.unregister(monitor_downloads)

def init_test_thumbnails():
    print(">>>>>>>>>>>>>>>>>>>>>>> INIT TexLIB")
    previews_collection = bpy.utils.previews.new()

    file_path = get_addon_filepath()

    mat_items = ("Asphalt001.png", "Asphalt002.png", "Candy001.png", "Candy002.png")
    
    print(">> fp = "+file_path)

    dir_name = os.path.join(file_path, "previews") + os.sep

    for index, item in enumerate(mat_items):
        file = dir_name + item
        print(">> fp = ", file)

        loaded = previews_collection.load(item, file, 'IMAGE')

        
        preview_items.append((item.split(".")[0], item, "", loaded.icon_id, index))

        # Scene.ambient_browser.shaders_previews.

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


if __name__ == "__main__":
    register()