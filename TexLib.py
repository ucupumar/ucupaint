from .common import * 
from .lib import *

import bpy, threading, os, requests
from bpy.props import *


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

class AmbientOp(bpy.types.Operator):
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


class TexLibBrowser(bpy.types.Panel):
    bl_label = "Texlib Browser"
    bl_idname = "TEXLIB_PT_AmbientCG"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Ucupaint"
    

    def draw(self, context):
        layout = self.layout
        amb_br = context.scene.ambient_browser
        layout.prop(amb_br, "input_search")
        layout.operator("texlib.op")
        layout.prop(amb_br, "progress", slider=True, text="Download")

        layout.template_icon_view(amb_br, "shaders_previews", show_labels=True,scale = 7, scale_popup = 5)

        layout.label(text="download "+str(amb_br.persen))

classes = [TexLibProps, TexLibBrowser, AmbientOp]
def register():
    for cl in classes:
        bpy.utils.register_class(cl)

    print("INIT TexLIB")
    previews_collection = bpy.utils.previews.new()

    file_path = get_addon_filepath()
    
    print(">> fp = "+file_path)

    dir_name = os.path.join(file_path, "previews") + os.sep

    print(">> fp = "+dir_name)
    file00 = dir_name + 'Asphalt001.png'
    file01 = dir_name + 'Asphalt002.png'
    print(">> fp = ", file00)

    as0 = previews_collection.load('Asphalt001', file00, 'IMAGE')
    as1 = previews_collection.load('Asphalt002', file01, 'IMAGE')

    preview_items.append(('Asphalt001.png', 'Asphalt001.png', "", as0.icon_id, 0))
    preview_items.append(('Asphalt002.png', 'Asphalt002.png', "", as1.icon_id, 1))


    bpy.types.Scene.ambient_browser = bpy.props.PointerProperty(type= TexLibProps)

    # bpy.app.timers.register(monitor_downloads, first_interval=1, persistent=True)    

def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
    del bpy.types.Scene.ambient_browser
    # Unregister the downloads timer
    # if bpy.app.timers.is_registered(monitor_downloads):
    #     bpy.app.timers.unregister(monitor_downloads)


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