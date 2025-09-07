
import bpy, threading, os, shutil

from bpy.types import Operator
from bpy.props import StringProperty, IntProperty, BoolProperty

from .. import Layer
from ..common import * 

from .downloader import download_stream, get_thread_id, get_thread, get_addon_dir
from .downloader import threads

from .properties import assets_library, TexLibProps, DownloadQueue,  get_textures_dir, cancel_searching, get_cat_asset_lib, get_preview_dir, retrieve_asset_library, get_os_config_dir, get_library_name

class TexLibAddToUcupaint(Operator, Layer.BaseMultipleImagesLayer):
    """Open Multiple Textures to Layer Ucupaint"""

    bl_label = "Add to Ucupaint"
    bl_idname = "texlib.add_to_ucupaint"

    attribute:StringProperty()
    id:StringProperty()
   
    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def invoke(self, context, event):
        self.invoke_operator(context)
        return context.window_manager.invoke_props_dialog(self, width=320)
    
    def check(self, context):
        return self.check_operator(context)

    def draw(self, context):
        self.draw_operator(context)
    
    def execute(self, context):
        directory = os.path.join(get_textures_dir(context), self.id, self.attribute)
        import_list = os.listdir(directory)

        if not self.open_images_to_single_layer(context, directory, import_list):
            return {'CANCELLED'}

        return {'FINISHED'}

class TexLibCancelDownload(Operator):
    """Cancel downloading textures"""

    bl_label = ""
    bl_idname = "texlib.cancel"
    attribute:StringProperty()
    id:StringProperty()

    def execute(self, context:bpy.context):
        thread_id = get_thread_id(self.id, self.attribute)
        thread = get_thread(thread_id)

        if thread == None:
            return {'CANCELLED'}
        thread.cancel = True

        texlib:TexLibProps = context.window_manager.ytexlib
        dwn:DownloadQueue
        for dwn in texlib.downloads:
            if dwn.asset_id ==  self.id and dwn.asset_attribute == self.attribute:
                dwn.alive = False
                return {'FINISHED'}
            
        return {'CANCELLED'}

class TexLibRemoveTextureAttribute(Operator):
    """Remove existing textures"""

    bl_label = "Remove Textures"
    bl_idname = "texlib.remove_attribute"
    attribute:StringProperty()
    id:StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="Are you sure to remove this texture?")
 
    def execute(self, context:bpy.context):
        dir_up = os.path.join(get_textures_dir(context), self.id)
        dir = os.path.join(dir_up, self.attribute)
        # print("item", self.id," | attr", self.attribute, " | file ", dir)
        print("remove dir: ", dir)  
        print("remove parent: ", dir_up)  
        # remove folder
        if os.path.exists(dir):
            for root, dirs, files in os.walk(dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(dir)

            # remove parent folder if empty
            if not os.listdir(dir_up):
                os.rmdir(dir_up)
                my_list = context.window_manager.ytexlib.downloaded_material_items
                my_list.remove(my_list.find(self.id))

            retrieve_asset_library(context)
            
            return {'FINISHED'}
        return {'CANCELLED'}
    
class TexLibDownload(Operator):
    """Download textures from source"""

    bl_label = ""
    bl_idname = "texlib.download"
    
    attribute:StringProperty()
    path_download:StringProperty()
    id:StringProperty()
    file_exist:BoolProperty(default=False)

    def invoke(self, context, event):
        if self.file_exist:
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)
    
    def draw(self, context:bpy.context):
        layout = self.layout

        layout.label(text="Already downloaded. Overwrite?", icon="QUESTION")

    def execute(self, context):
        asset_item = assets_library[self.id]
        attribute_item = asset_item.attributes[self.attribute]
        link = attribute_item.asset.link
        directory = os.path.join( get_textures_dir(context), self.id, self.attribute)
        file_name = os.path.join(directory, attribute_item.asset.file_name)

        asset_cats_file = get_cat_asset_lib(context)
        print("asset cat file: ", asset_cats_file)
        has_cat_id = False

        if os.path.exists(asset_cats_file):
            cat_id = get_cat_id(asset_cats_file)
            has_cat_id = cat_id != "" # replace existing with template cat
        
        if not has_cat_id:
            template_asst = os.path.join(get_addon_dir(), "blender_assets.cats.txt")
            shutil.copy(template_asst, asset_cats_file)
            
        cat_id = get_cat_id(asset_cats_file)
        print("cat id: ", cat_id)

        if not os.path.exists(directory):
            # print("make dir "+directory)
            os.makedirs(directory)

        prev_dir = get_preview_dir(context)
        thumb_file = os.path.join(prev_dir, self.id+".png")
        # copy preview file
        if os.path.exists(thumb_file):
            dest_thumb = os.path.join(directory, self.id+".png")
            print("copy file ", thumb_file, " to ", dest_thumb)
            shutil.copyfile(thumb_file, dest_thumb)

        links = [link]
        file_names = [file_name]

        for idx, attr in enumerate(attribute_item.textures):  
            txt_file = os.path.join(directory, attr.file_name)
            txr_dir = os.path.dirname(txt_file)
            if not os.path.exists(txr_dir):
                os.makedirs(txr_dir)

            links.append(attr.link)
            file_names.append(txt_file)

        thread_id = get_thread_id(self.id, self.attribute)
        new_thread = threading.Thread(target=download_stream, args=(links,file_names,thread_id,))
        new_thread.progress = 0
        new_thread.cancel = False
        threads[thread_id] = new_thread

        new_thread.start()

        texlib:TexLibProps = context.window_manager.ytexlib
        new_dwn:DownloadQueue = texlib.downloads.add()
        new_dwn.asset_cat_id = cat_id
        if len(asset_item.tags) > 0:
            new_dwn.tags = ";".join(asset_item.tags) 
        else:
            new_dwn.tags = ""
            
        new_dwn.asset_id = self.id
        new_dwn.file_path = file_name
        new_dwn.source_type = asset_item.source_type
        new_dwn.asset_attribute = self.attribute
        new_dwn.alive = True
        new_dwn.file_size = attribute_item.asset.size
        new_dwn.progress = 0

        return {'FINISHED'}

class TexLibCancelSearch(Operator):
    bl_idname = "texlib.cancel_search"
    bl_label = ""
    
    def execute(self, context):
        cancel_searching(context)
        return{'FINISHED'}
    
class TexLibRemoveTextureAllAttributes(Operator):
    bl_idname = "texlib.remove_attributes"
    bl_label = ""
    id:StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="Are you sure to remove this textures?")
 
    def execute(self, context):
        dir = get_textures_dir(context) + self.id 
        print("item", self.id, " | file ", dir)
        my_list = context.window_manager.ytexlib.downloaded_material_items
        my_list.remove(my_list.find(self.id))
        # remove folder
        if os.path.exists(dir):
            for root, dirs, files in os.walk(dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(dir)
            return {'FINISHED'}
        
        return {'CANCELLED'}

class ShowFilePathPreference(Operator):
    bl_idname = "texlib.show_pref"
    bl_label = "Show Preference"
    
    def execute(self, context):
        bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
        bpy.context.preferences.active_section = 'FILE_PATHS'
        return{'FINISHED'}
    
class CreateAssetDirectory(Operator):
    bl_idname = "texlib.create_dir"
    bl_label = "Setup Asset Directory"
    
    def execute(self, context):
        print("create asset directory "+get_os_config_dir())
        asset_library_path = get_os_config_dir()
        # Create the directory if it doesn't exist
        if not os.path.exists(asset_library_path):
            os.makedirs(asset_library_path)
            print(f"Created directory: {asset_library_path}")
        else:
            print(f"Directory already exists: {asset_library_path}")
       
        # Add a new Asset Library
        bpy.ops.preferences.asset_library_add(directory=asset_library_path)
        context.preferences.filepaths.asset_libraries[-1].name = get_library_name()
        
        print(f"Added Asset Library: {asset_library_path}")
        
        return{'FINISHED'}


class ShowLibrary(Operator):
    bl_idname = "texlib.show_lib"
    bl_label = "Show Asset Browser"

    area_type = "FILE_BROWSER"
    area_ui_type = "ASSETS"
    
    @classmethod
    def poll(cls, context):
        existing_lib = False
        for area in context.screen.areas:
            if area.type == ShowLibrary.area_type and area.ui_type == ShowLibrary.area_ui_type: # 'VIEW_3D', 'CONSOLE', 'INFO' etc. 
                existing_lib = True
                break
        return not existing_lib
    
    def execute(self, context):
        existing_lib = False
        for area in context.screen.areas:
            if area.type == self.area_type and area.ui_type == self.area_ui_type: # 'VIEW_3D', 'CONSOLE', 'INFO' etc. 
                existing_lib = True
                break

        # for area in context.screen.areas:
        #     print(area.type, " >> ", area.ui_type)
        if not existing_lib:
            # with context.temp_override(area=area):
            bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.3)
            # Get the new area
            new_area = bpy.context.screen.areas[-1]

            # Change the type of the new area to FILE_BROWSER
            new_area.type = self.area_type
            new_area.ui_type = self.area_ui_type

        return{'FINISHED'}

class DebugOp(Operator):
    bl_idname = "texlib.debug"
    bl_label = "Check Debug"

    def execute(self, context):
        lib_dir = get_cat_asset_lib(context) 
        
        content = get_cat_id(lib_dir)
        print("lib dir: ", lib_dir, "=", content)

        retrieve_asset_library(context)
        return{'FINISHED'}
    
def get_cat_id(file_path:str, category:str = "Materials") -> str:
    retval = ""
    print("read file: ", file_path)

    # read file
    with open(file_path, "r") as file:
        lines = file.readlines()
        for line in lines:
            # print(line)
            line = line.strip()
            if not line:
                continue  # Empty lines
            if line.startswith("#"):
                continue
            if line.startswith("VERSION"):
                continue

            parts = line.split(":")
            uuid, path = parts[:2]
            crumbs = path.split("/")
            
            retval = uuid  # In case the asset is not in any categories, revert to top level type catalog

            if len(crumbs) == 1:
                # Ignore top level type catalog from here on
                continue

            # Match catalog only if asset has all categories in its tree
            match = True
            for cat in crumbs[1:]:
                if cat.lower() != category.lower():
                    match = False

            if not match:
                continue

            return uuid

    return retval

classes = [
    TexLibAddToUcupaint,
	TexLibCancelDownload,
	TexLibRemoveTextureAttribute,
	TexLibDownload,
	TexLibCancelSearch,
	TexLibRemoveTextureAllAttributes,
    ShowFilePathPreference,
    CreateAssetDirectory,
    ShowLibrary,
    DebugOp
]

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
        
def unregister():
	for cls in classes:
		bpy.utils.unregister_class(cls)