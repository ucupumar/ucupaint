import bpy, os, subprocess, sys
import tempfile
from bpy.props import *
from bpy_extras.io_utils import ExportHelper
from .common import *
import time
from . import UDIM

def save_float_image(image):
    original_path = image.filepath

    # Create temporary scene
    tmpscene = bpy.data.scenes.new('Temp Scene')

    # Set settings
    settings = tmpscene.render.image_settings

    # Check current extensions
    for form, ext in format_extensions.items():
        if image.filepath.endswith(ext):
            if form == 'OPEN_EXR_MULTILAYER' and image.type != 'MULTILAYER': continue
            settings.file_format = form
            break
    
    if settings.file_format in {'OPEN_EXR', 'OPEN_EXR_MULTILAYER'}:
        settings.exr_codec = 'ZIP'
        settings.color_depth = '32'
    elif settings.file_format in {'PNG', 'TIFF'}:
        settings.color_depth = '16'

    #ori_colorspace = image.colorspace_settings.name
    full_path = bpy.path.abspath(image.filepath)
    image.save_render(full_path, scene=tmpscene)
    # HACK: If image still dirty after saving, save using standard save method
    if image.is_dirty: image.save()
    image.source = 'FILE'

    # Delete temporary scene
    remove_datablock(bpy.data.scenes, tmpscene)

def pack_float_image(image):
    original_path = image.filepath

    # Create temporary scene
    tmpscene = bpy.data.scenes.new('Temp Scene')

    # Set settings
    settings = tmpscene.render.image_settings

    #if image.filepath == '':
    #if original_path == '':
    if bpy.path.basename(original_path) == '':
        if hasattr(image, 'use_alpha') and image.use_alpha:
            settings.file_format = 'PNG'
            settings.color_depth = '16'
            #settings.color_mode = 'RGBA'
            settings.compression = 15
            image_name = '_temp_image.png'
        else:
            settings.file_format = 'HDR'
            settings.color_depth = '32'
            image_name = '_temp_image.hdr'
    else:
        settings.file_format = image.file_format
        if image.file_format in {'CINEON', 'DPX'}:
            settings.color_depth = '10'
        elif image.file_format in {'TIFF'}:
            settings.color_depth = '16'
        elif image.file_format in {'HDR', 'OPEN_EXR_MULTILAYER', 'OPEN_EXR'}:
            settings.color_depth = '32'
        else:
            settings.color_depth = '16'
        image_name = bpy.path.basename(original_path)

    temp_filepath = os.path.join(tempfile.gettempdir(), image_name)

    # Save image
    image.save_render(temp_filepath, scene=tmpscene)
    image.source = 'FILE'
    image.filepath = temp_filepath
    if image.file_format == 'PNG':
        image.colorspace_settings.name = get_srgb_name()
    else: image.colorspace_settings.name = get_noncolor_name()

    # Delete temporary scene
    remove_datablock(bpy.data.scenes, tmpscene)

    # Pack image
    image.pack()

    #image.reload()

    # Bring back to original path
    image.filepath = original_path
    os.remove(temp_filepath)

def clean_object_references(image):
    removed_references = []
    if image.yia.is_image_atlas:
        for segment in image.yia.segments:
            if segment.bake_info.is_baked:

                # Check if selected objects data are still accessible on any view layers
                indices = []
                for i, o in enumerate(segment.bake_info.selected_objects):
                    if o.object:
                        if is_bl_newer_than(2, 80):
                            if not any([s for s in bpy.data.scenes if o.object.name in s.collection.all_objects]):
                                removed_references.append(o.object.name)
                                indices.append(i)
                        else:
                            if not any([s for s in bpy.data.scenes if o.object.name in s.objects]):
                                removed_references.append(o.object.name)
                                indices.append(i)

                for i in reversed(indices):
                    segment.bake_info.selected_objects.remove(i)

                # Check if other object's data is still accessible on any view layers
                indices = []
                for i, o in enumerate(segment.bake_info.other_objects):
                    if o.object:
                        if is_bl_newer_than(2, 80):
                            if not any([s for s in bpy.data.scenes if o.object.name in s.collection.all_objects]):
                                removed_references.append(o.object.name)
                                indices.append(i)
                        else:
                            if not any([s for s in bpy.data.scenes if o.object.name in s.objects]):
                                removed_references.append(o.object.name)
                                indices.append(i)

                for i in reversed(indices):
                    segment.bake_info.other_objects.remove(i)

    elif image.y_bake_info.is_baked:

        if image.y_bake_info.is_baked:

            # Check if selected objects data are still accessible on any view layers
            indices = []
            for i, o in enumerate(image.y_bake_info.selected_objects):
                if o.object:
                    if is_bl_newer_than(2, 80):
                        if not any([s for s in bpy.data.scenes if o.object.name in s.collection.all_objects]):
                            removed_references.append(o.object.name)
                            indices.append(i)
                    else:
                        if not any([s for s in bpy.data.scenes if o.object.name in s.objects]):
                            removed_references.append(o.object.name)
                            indices.append(i)
            for i in reversed(indices):
                image.y_bake_info.selected_objects.remove(i)

            # Check if other object's data is still accessible on any view layers
            indices = []
            for i, o in enumerate(image.y_bake_info.other_objects):
                if o.object:
                    if is_bl_newer_than(2, 80):
                        if not any([s for s in bpy.data.scenes if o.object.name in s.collection.all_objects]):
                            removed_references.append(o.object.name)
                            indices.append(i)
                    else:
                        if not any([s for s in bpy.data.scenes if o.object.name in s.objects]):
                            removed_references.append(o.object.name)
                            indices.append(i)
            for i in reversed(indices):
                image.y_bake_info.other_objects.remove(i)

    for r in removed_references:
        print('Reference for', r, "is removed because it's no longer found!")

def create_temp_scene():
    print('INFO: Creating temporary scene for saving some images...')
    tmpscene = bpy.data.scenes.new('Temp Save Scene')

    try: tmpscene.view_settings.view_transform = 'Standard'
    except: print('EXCEPTIION: Cannot set view transform on temporary save scene!')
    try: tmpscene.render.image_settings.file_format = 'PNG'
    except: print('EXCEPTIION: Cannot set file format on temporary save scene!')

    return tmpscene

def save_pack_all(yp):

    images = get_yp_images(yp, get_baked_channels=True, check_overlay_normal=True)
    packed_float_images = []

    # Temporary scene for some saving hack
    tmpscene = None
    temp_udim_dir = UDIM.get_temp_udim_dir()

    # Save/pack images
    for image in images:
        if not image: continue

        # There's a need to check if there's empty tile to make sure the image will be packed correctly
        # NOTE: There's actually no need to do this for Blender 4.1 onward,
        # but empty tile will still be removed just in case it will cause unexpected problem
        force_pack = False
        if UDIM.is_udim_supported() and image.source == 'TILED' and UDIM.remove_empty_tiles(image) and UDIM.is_using_temp_dir(image):
            force_pack = True

        if not image.is_dirty and not force_pack: continue
        T = time.time()

        if image.packed_file or image.filepath == '' or force_pack:
            if is_bl_newer_than(2, 80):

                # HACK: Some cases need images to be saved first before packing on Blender pre 4.1
                temp_saved = False
                if force_pack or (UDIM.is_udim_supported() and not is_bl_newer_than(4, 1) and image.source == 'TILED'):
                    if not tmpscene: tmpscene = create_temp_scene()

                    if image.filepath != '':
                        path = bpy.path.abspath(image.filepath)
                    else: path = bpy.path.abspath(UDIM.get_udim_filepath(image.name, temp_udim_dir))

                    image.save_render(path, scene=tmpscene)

                    # Set the filepath to the image
                    image.filepath = path
                    try: image.filepath = bpy.path.relpath(path)
                    except: pass

                    temp_saved = True
                    
                image.pack()

                if temp_saved:
                    # Remove file if they are using temporary directory
                    if UDIM.is_using_temp_dir(image):
                        UDIM.remove_udim_files_from_disk(image, temp_udim_dir, True)

            else:
                if image.is_float:
                    pack_float_image(image)
                    packed_float_images.append(image)
                else: 
                    image.pack(as_png=True)

            print('INFO:', image.name, 'image is packed in', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        else:
            if image.is_float:
                save_float_image(image)
            else:
                # BLENDER BUG: Blender 3.3 has wrong srgb if not packed first
                if is_bl_newer_than(3, 3) and image.colorspace_settings.name in {'Linear', get_noncolor_name()}:

                    # Create temporary scene
                    if not tmpscene: tmpscene = create_temp_scene()

                    # Get image path
                    path = bpy.path.abspath(image.filepath)

                    # Pack image first
                    image.pack()
                    image.colorspace_settings.name = get_srgb_name()

                    # Remove old files to avoid caching (?)
                    try: os.remove(path)
                    except Exception as e: print(e)
                    
                    # Then unpack
                    default_dir, default_dir_found, default_filepath, temp_path, unpacked_path = unpack_image(image, path)

                    # Save image
                    image.save_render(path, scene=tmpscene)

                    # Set the filepath to the image
                    image.filepath = path
                    if bpy.data.filepath != '':
                        try: image.filepath = bpy.path.relpath(path)
                        except: pass

                    # Bring back linear
                    image.colorspace_settings.name = get_noncolor_name()

                    # Remove unpacked images in Blender 3.3 
                    remove_unpacked_image_path(image, path, default_dir, default_dir_found, default_filepath, temp_path, unpacked_path)

                    print('INFO:', image.name, 'image is saved in', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

                else:
                    try:
                        ori_colorspace = image.colorspace_settings.name
                        image.save()
                        image.colorspace_settings.name = ori_colorspace

                        print('INFO:', image.name, 'image is saved in', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
                    except Exception as e:
                        print(e)

    # Delete temporary scene
    if tmpscene:
        print('INFO: Deleting temporary scene used for saving some images...')
        remove_datablock(bpy.data.scenes, tmpscene)

    # HACK: For some reason active float image will glitch after auto save
    # This is only happen if active object is in texture paint mode
    obj = bpy.context.object
    if len(yp.layers) > 0 and obj and obj.mode == 'TEXTURE_PAINT':
        layer = yp.layers[yp.active_layer_index]
        if layer.type == 'IMAGE':
            source = get_layer_source(layer)
            image = source.image
            if image in packed_float_images:
                ypui = bpy.context.window_manager.ypui
                ypui.refresh_image_hack = True

    # Clean object reference on images
    if is_bl_newer_than(2, 79):
        for image in images:
            clean_object_references(image)

class YCopyImagePathToClipboard(bpy.types.Operator):
    bl_idname = "wm.copy_image_path_to_clipboard"
    bl_label = "Copy Image Path To Clipboard"
    bl_description = get_addon_title() + " Copy the image file path to the system clipboard"

    clipboard_text = bpy.props.StringProperty()

    def execute(self, context):
        context.window_manager.clipboard = self.clipboard_text
        self.report({'INFO'}, "Copied: " + self.clipboard_text)
        return {'FINISHED'}

class YOpenContainingImageFolder(bpy.types.Operator):
    bl_idname = "wm.open_containing_image_folder"
    bl_label = "Open Containing Image Folder"
    bl_description = get_addon_title() + " Open the folder containing the image file and highlight it"

    file_path = bpy.props.StringProperty()

    def execute(self, context):
        filepath = bpy.path.abspath(self.file_path)
        if not os.path.exists(filepath):
            self.report({'ERROR'}, "File does not exist")
            return {'CANCELLED'}
        try:
            # Add more branches below for different operating systems
            if sys.platform == 'win32':  # Windows
                subprocess.call(["explorer", "/select,", filepath])
            elif sys.platform == 'darwin': # Mac
                subprocess.call(["open", "-R", filepath])
            elif sys.platform == 'linux': # Linux
                subprocess.check_call(['dbus-send', '--session', '--print-reply', '--dest=org.freedesktop.FileManager1', '--type=method_call', '/org/freedesktop/FileManager1', 'org.freedesktop.FileManager1.ShowItems', 'array:string:file://'+os.path.normpath(filepath), 'string:""'])
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}

class YInvertImage(bpy.types.Operator):
    """Invert Image"""
    bl_idname = "wm.y_invert_image"
    bl_label = "Invert Image"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image

    def execute(self, context):

        if context.image.yia.is_image_atlas:
            self.report({'ERROR'}, 'Cannot invert image atlas!')
            return {'CANCELLED'}

        # For some reason this no longer works since Blender 2.82, but worked again in Blender 4.2
        if not is_bl_newer_than(2, 82) or is_bl_newer_than(4, 2):
            override = bpy.context.copy()
            override['edit_image'] = context.image
            if is_bl_newer_than(4):
                with bpy.context.temp_override(**override):
                    bpy.ops.image.invert(invert_r=True, invert_g=True, invert_b=True)
            else: bpy.ops.image.invert(override, invert_r=True, invert_g=True, invert_b=True)
        else:
            ori_area_type = context.area.type
            context.area.type = 'IMAGE_EDITOR'

            space = context.area.spaces[0]
            space.image = context.image
                
            bpy.ops.image.invert(invert_r=True, invert_g=True, invert_b=True)

            context.area.type = ori_area_type

        return {'FINISHED'}

class YRefreshImage(bpy.types.Operator):
    """Reload Image"""
    bl_idname = "wm.y_reload_image"
    bl_label = "Reload Image"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image

    def execute(self, context):
        # Reload image
        context.image.reload()

        # Refresh viewport and image editor
        for area in context.screen.areas:
            if area.type in ['VIEW_3D', 'IMAGE_EDITOR', 'NODE_EDITOR']:
                area.tag_redraw()

        return {'FINISHED'}

class YPackImage(bpy.types.Operator):
    """Pack Image"""
    bl_idname = "wm.y_pack_image"
    bl_label = "Pack Image"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image and not context.image.packed_file

    def execute(self, context):

        T = time.time()

        # Save file to temporary place first if image is float
        if is_bl_newer_than(2, 80):
            context.image.pack()
        else:
            if context.image.is_float:
                pack_float_image(context.image)
            else: context.image.pack(as_png=True)

        context.image.filepath = ''

        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp

        if yp.use_baked and yp.active_channel_index < len(yp.channels):
            ch = yp.channels[yp.active_channel_index]
            if ch.type == 'NORMAL':

                baked_disp = tree.nodes.get(ch.baked_disp)
                if baked_disp and baked_disp.image and not baked_disp.image.packed_file:
                    if is_bl_newer_than(2, 80):
                        baked_disp.image.pack()
                    else:
                        if baked_disp.image.is_float:
                            pack_float_image(baked_disp.image)
                        else: baked_disp.image.pack(as_png=True)

                    baked_disp.image.filepath = ''

                baked_vdisp = tree.nodes.get(ch.baked_vdisp)
                if baked_vdisp and baked_vdisp.image and not baked_vdisp.image.packed_file:
                    if is_bl_newer_than(2, 80):
                        baked_vdisp.image.pack()
                    else:
                        if baked_vdisp.image.is_float:
                            pack_float_image(baked_vdisp.image)
                        else: baked_vdisp.image.pack(as_png=True)

                    baked_vdisp.image.filepath = ''

                if not is_overlay_normal_empty(yp):
                    baked_normal_overlay = tree.nodes.get(ch.baked_normal_overlay)
                    if baked_normal_overlay and baked_normal_overlay.image and not baked_normal_overlay.image.packed_file:
                        if is_bl_newer_than(2, 80):
                            baked_normal_overlay.image.pack()
                        else:
                            if baked_normal_overlay.image.is_float:
                                pack_float_image(baked_normal_overlay.image)
                            else: baked_normal_overlay.image.pack(as_png=True)

                    baked_normal_overlay.image.filepath = ''

        print('INFO:', context.image.name, 'image is packed in', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

        return {'FINISHED'}

class YSaveImage(bpy.types.Operator):
    """Save Image"""
    bl_idname = "wm.y_save_image"
    bl_label = "Save Image"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image and context.image.filepath != '' and not context.image.packed_file

    def execute(self, context):
        ori_colorspace = context.image.colorspace_settings.name
        if context.image.is_float:
            save_float_image(context.image)
        else:
            context.image.save()
        context.image.colorspace_settings.name = ori_colorspace
        return {'FINISHED'}

format_extensions = {
    'BMP' : '.bmp',
    'IRIS' : '.rgb',
    'PNG' : '.png',
    'JPEG' : '.jpg',
    'JPEG2000' : '.jp2',
    'TARGA' : '.tga',
    'TARGA_RAW' : '.tga',
    'CINEON' : '.cin',
    'DPX' : '.dpx',
    'OPEN_EXR_MULTILAYER' : '.exr',
    'OPEN_EXR' : '.exr',
    'HDR' : '.hdr',
    'TIFF' : '.tif',
    'WEBP' : '.webp',
}

def color_mode_items(self, context):
    items = []

    if self.file_format in {'BMP', 'IRIS', 'PNG', 'JPEG', 'TARGA', 'TARGA_RAW', 'TIFF'}:
        items.append(('BW', 'BW', ''))

    items.append(('RGB', 'RGB', ''))

    if self.file_format not in {'BMP', 'JPEG', 'CINEON', 'HDR'}:
        items.append(('RGBA', 'RGBA', ''))

    return items

def color_depth_items(self, context):
    if self.file_format in {'PNG', 'TIFF'}:
        items = (
            ('8', '8', ''),
            ('16', '16', '')
        )
    elif self.file_format in {'JPEG2000'}:
        items = (
            ('8', '8', ''),
            ('12', '12', ''),
            ('16', '16', '')
        )
    elif self.file_format in {'DPX'}:
        items = (
            ('8', '8', ''),
            ('10', '10', ''),
            ('12', '12', ''),
            ('16', '16', '')
        )
    elif self.file_format in {'OPEN_EXR_MULTILAYER', 'OPEN_EXR'}:
        items = (
            ('16', 'Float (Half)', ''),
            ('32', 'Float (Full)', '')
        )
    else:
        items = (
            ('8', '8', ''),
            ('10', '10', ''),
            ('12', '12', ''),
            ('16', '16', ''),
            ('32', '32', '')
        )

    return items

def update_save_as_file_format(self, context):
    if self.file_format in {'BMP', 'JPEG', 'CINEON', 'HDR'}:
        self.color_mode = 'RGB'
    else: self.color_mode = 'RGBA'

    if self.file_format in {'BMP', 'IRIS', 'PNG', 'JPEG', 'JPEG2000', 'TARGA', 'TARGA_RAW', 'WEBP'}:
        self.color_depth = '8'
    elif self.file_format in {'CINEON', 'DPX'}:
        self.color_depth = '10'
    elif self.file_format in {'TIFF'}:
        self.color_depth = '16'
    elif self.file_format in {'HDR', 'OPEN_EXR_MULTILAYER', 'OPEN_EXR'}:
        self.color_depth = '32'

    if self.is_float and self.file_format in {'PNG', 'JPEG2000'}:
        self.color_depth = '16'

def unpack_image(image, filepath):

    # Get blender default unpack directory
    default_dir = os.path.join(os.path.abspath(bpy.path.abspath('//')), 'textures')

    # Check if default directory is available or not, delete later if not found now
    default_dir_found = os.path.isdir(default_dir)

    # Blender always unpack at \\textures\file.ext
    if image.filepath == '':
        default_filepath = os.path.join(default_dir, image.name)
    else: default_filepath = os.path.join(default_dir, bpy.path.basename(image.filepath))

    # Check if file with default path is already available
    temp_path = ''
    if os.path.isfile(default_filepath) and default_filepath != filepath:
        temp_path = os.path.join(default_dir, '__TEMP__')
        os.rename(default_filepath, temp_path)

    # Unpack the file
    image.unpack()
    unpacked_path = bpy.path.abspath(image.filepath)

    # HACK: Unpacked path sometimes has inconsistent backslash
    folder, file = os.path.split(unpacked_path)
    unpacked_path = os.path.join(folder, file)

    return default_dir, default_dir_found, default_filepath, temp_path, unpacked_path

def remove_unpacked_image_path(image, filepath, default_dir, default_dir_found, default_filepath, temp_path, unpacked_path):

    # Remove unpacked file
    if filepath != unpacked_path:
        if image.source == 'TILED':
            for tile in image.tiles:
                upath = unpacked_path.replace('<UDIM>', str(tile.number))
                try: os.remove(upath)
                except Exception as e: print(e)
        else:
            os.remove(unpacked_path)

    # Rename back temporary file
    if temp_path != '':
        if temp_path != filepath:
            os.rename(temp_path, default_filepath)
        else: os.remove(temp_path)

    # Delete default directory if not found before
    if not default_dir_found:
        os.rmdir(default_dir)

class YSaveAllBakedImages(bpy.types.Operator):
    """Save All Baked Images to directory"""
    bl_idname = "wm.y_save_all_baked_images"
    bl_label = "Save All Baked Images"
    bl_options = {'REGISTER', 'UNDO'}

    # Define this to tell 'fileselect_add' that we want a directoy
    directory = bpy.props.StringProperty(
        name = 'Outdir Path',
        description = 'Where I will save my stuff'
        # subtype='DIR_PATH' is not needed to specify the selection mode.
        # But this will be anyway a directory path.
    )

    remove_whitespaces = bpy.props.BoolProperty(
        name = 'Remove Whitespaces',
        description = 'Remove whitespaces from baked image names',
        default = False
    )

    file_format = EnumProperty(
        name = 'File Format',
        items = (
            ('PNG', 'PNG', '', 'IMAGE_DATA', 0),
            ('TIFF', 'TIFF', '', 'IMAGE_DATA', 1),
            ('OPEN_EXR', 'OpenEXR', '', 'IMAGE_DATA', 2)
        ),
        default = 'PNG'
    )

    copy = BoolProperty(
        name = 'Copy',
        description = 'Create a new image file without modifying the current image in Blender',
        default = False
    )

    def invoke(self, context, event):
        # Open browser, take reference to 'self' read the path to selected
        # file, put path in predetermined self fields.
        # See: https://docs.blender.org/api/current/bpy.types.WindowManager.html#bpy.types.WindowManager.fileselect_add
        context.window_manager.fileselect_add(self)
        # Tells Blender to hang on for the slow user input
        return {'RUNNING_MODAL'}

    def draw(self, context):
        split = split_layout(self.layout, 0.4)
        col = split.column()
        col.label(text='Image Format:')
        col = split.column()
        col.prop(self, 'file_format', text='')

        self.layout.prop(self, 'copy')

    def execute(self, context):

        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp

        tmpscene = bpy.data.scenes.new('Temp Save As Scene')
        settings = tmpscene.render.image_settings

        # Blender 2.80 has filmic as default color settings, change it to standard
        if is_bl_newer_than(2, 80):
            tmpscene.view_settings.view_transform = 'Standard'

        images = []

        height_root_ch = get_root_height_channel(yp)

        # Baked images
        for ch in yp.channels:
            if ch.no_layer_using: continue

            baked = tree.nodes.get(ch.baked)
            if baked and baked.image:
                images.append(baked.image)

            if ch == height_root_ch:

                baked_disp = tree.nodes.get(ch.baked_disp)
                if baked_disp and baked_disp.image:
                    images.append(baked_disp.image)

                baked_vdisp = tree.nodes.get(ch.baked_vdisp)
                if baked_vdisp and baked_vdisp.image:
                    images.append(baked_vdisp.image)

                if not is_overlay_normal_empty(yp):
                    baked_normal_overlay = tree.nodes.get(ch.baked_normal_overlay)
                    if baked_normal_overlay and baked_normal_overlay.image:
                        images.append(baked_normal_overlay.image)

        # Custom bake target images
        for bt in yp.bake_targets:
            image_node = tree.nodes.get(bt.image_node)
            if image_node and image_node.image not in images:
                images.append(image_node.image)

        original_image_names = []
        original_names = []
        if self.copy:
            copied_images = []
            for image in images:
                ori_name = image.name
                image_copy = duplicate_image(image, ondisk_duplicate=False)
                image.name += '____'
                image_copy.name = ori_name
                original_image_names.append(image.name)
                original_names.append(ori_name)
                copied_images.append(image_copy)

            images = copied_images

        for image in images:

            settings.file_format = self.file_format
            settings.color_depth = '8' if settings.file_format != 'OPEN_EXR' else '16'
            if image.is_float:
                settings.color_depth = '16' if settings.file_format != 'OPEN_EXR' else '32'
            if settings.file_format == 'OPEN_EXR':
                settings.exr_codec = 'ZIP'

            if image.filepath == '' or '.<UDIM>.' in image.filepath:
                image_name = image.name
                # Remove addon title from the file names
                if image_name.startswith(get_addon_title() + ' '):
                    image_name = image_name.replace(get_addon_title() + ' ', '')
                filename = image_name
                filename += '.<UDIM>' if '.<UDIM>.' in image.filepath else ''
                filename += format_extensions[settings.file_format]
            else:
                filename = bpy.path.basename(image.filepath)
                ext = os.path.splitext(filename)[1]

                if ext != format_extensions[settings.file_format]:
                    filename = filename.replace(ext, format_extensions[settings.file_format])

            if self.remove_whitespaces:
                filename = filename.replace(' ', '')

            path = os.path.join(self.directory, filename)

            # Need to pack first to save the image
            if image.is_dirty:
                if is_bl_newer_than(2, 80):
                    image.pack()
                else:
                    if image.is_float:
                        pack_float_image(image)
                    else: image.pack(as_png=True)

            # Some images need to set to srgb when saving
            ori_colorspace = image.colorspace_settings.name
            if not image.is_float and image.colorspace_settings.name != get_srgb_name():
                image.colorspace_settings.name = get_srgb_name()
            
            # Unpack image if image is packed (Only necessary for Blender 2.80 and lower)
            unpacked_to_disk = False
            if not is_bl_newer_than(2, 81) and bpy.data.filepath != '' and image.packed_file:
                unpacked_to_disk = True
                default_dir, default_dir_found, default_filepath, temp_path, unpacked_path = unpack_image(image, path)

            # Save image
            image.save_render(path, scene=tmpscene)

            # Set the filepath to the image
            image.filepath = path
            if bpy.data.filepath != '':
                try: image.filepath = bpy.path.relpath(path)
                except: pass

            # Set back colorspace settings
            if image.colorspace_settings.name != ori_colorspace:
                image.colorspace_settings.name = ori_colorspace

            # Remove temporarily unpacked image
            if unpacked_to_disk:
                remove_unpacked_image_path(image, path, default_dir, default_dir_found, default_filepath, temp_path, unpacked_path)

            # Remove packed flag
            if is_bl_newer_than(2, 81) and image.packed_file:
                image.unpack(method='REMOVE')

        # Remove copied images
        if self.copy:
            for image in reversed(images):
                remove_datablock(bpy.data.images, image)

        # Recover image names
        for i, ori_image_name in enumerate(original_image_names):
            ori_image = bpy.data.images.get(ori_image_name)
            ori_image.name = original_names[i]

        # Delete temporary scene
        remove_datablock(bpy.data.scenes, tmpscene)

        #print("Selected dir: '" + self.directory + "'")

        return {'FINISHED'}

def get_file_format_items():
    items = [
        ('BMP', 'BMP', '', 'IMAGE_DATA', 0),
        ('IRIS', 'Iris', '', 'IMAGE_DATA', 1),
        ('PNG', 'PNG', '', 'IMAGE_DATA', 2),
        ('JPEG', 'JPEG', '', 'IMAGE_DATA', 3),
        ('JPEG2000', 'JPEG 2000', '', 'IMAGE_DATA', 4),
        ('TARGA', 'Targa', '', 'IMAGE_DATA', 5),
        ('TARGA_RAW', 'Targa Raw', '', 'IMAGE_DATA', 6),
        ('CINEON', 'Cineon', '', 'IMAGE_DATA', 7),
        ('DPX', 'DPX', '', 'IMAGE_DATA', 8),
        ('OPEN_EXR_MULTILAYER', 'OpenEXR Multilayer', '', 'IMAGE_DATA', 9),
        ('OPEN_EXR', 'OpenEXR', '', 'IMAGE_DATA', 10),
        ('HDR', 'Radiance HDR', '', 'IMAGE_DATA', 11),
        ('TIFF', 'TIFF', '', 'IMAGE_DATA', 12)
    ]

    if is_bl_newer_than(3, 2):
        items.append(('WEBP', 'WebP', '', 'IMAGE_DATA', 13))

    return items

class YSaveAsImage(bpy.types.Operator, ExportHelper):
    """Save As Image"""
    bl_idname = "wm.y_save_as_image"
    bl_label = "Save As Image"
    bl_options = {'REGISTER', 'UNDO'}

    file_format = EnumProperty(
        name = 'File Format',
        items = get_file_format_items(),
        default = 'PNG',
        update = update_save_as_file_format
    )

    # File browser filter
    filter_folder = BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image = BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    display_type = EnumProperty(
        items = (
            ('FILE_DEFAULTDISPLAY', 'Default', ''),
            ('FILE_SHORTDISLPAY', 'Short List', ''),
            ('FILE_LONGDISPLAY', 'Long List', ''),
            ('FILE_IMGDISPLAY', 'Thumbnails', '')
        ),
        default = 'FILE_IMGDISPLAY',
        options = {'HIDDEN', 'SKIP_SAVE'}
    )

    copy = BoolProperty(
        name = 'Copy',
        description = 'Create a new image file without modifying the current image in Blender',
        default = False
    )

    relative = BoolProperty(
        name = 'Relative Path',
        description = 'Select the file relative to the blend file',
        default = True
    )

    color_mode = EnumProperty(
        name = 'Color Mode',
        items = color_mode_items
    )

    color_depth = EnumProperty(
        name = 'Color Depth',
        items = color_depth_items
    )

    tiff_codec = EnumProperty(
        name = 'Compression',
        items = (
            ('NONE', 'None', ''),
            ('DEFLATE', 'Deflate', ''),
            ('LZW', 'LZW', ''),
            ('PACKBITS', 'Pack Bits', ''),
        ),
        default = 'DEFLATE'
    )

    exr_codec = EnumProperty(
        name = 'Codec',
        items = (
            ('NONE', 'None', ''),
            ('PXR24', 'Pxr24 (lossy)', ''),
            ('ZIP', 'ZIP (lossless)', ''),
            ('PIZ', 'PIZ (lossless)', ''),
            ('RLE', 'RLE (lossless)', ''),
            ('ZIPS', 'ZIPS (lossless)', ''),
            ('DWAA', 'DWAA (lossy)', ''),
        ),
        default = 'ZIP'
    )

    jpeg2k_codec = EnumProperty(
        name = 'Codec',
        items = (
            ('JP2', 'JP2', ''),
            ('J2K', 'J2K', ''),
        ),
        default = 'JP2'
    )

    compression = IntProperty(name='Compression', default=15, min=0, max=100, subtype='PERCENTAGE')
    quality = IntProperty(name='Quality', default=90, min=0, max=100, subtype='PERCENTAGE')

    use_jpeg2k_cinema_48 = BoolProperty(name='Cinema 48', default=False)
    use_jpeg2k_cinema_preset = BoolProperty(name='Cinema', default=False)
    use_jpeg2k_ycc = BoolProperty(name='YCC', default=False)
    use_cineon_log = BoolProperty(name='Log', default=False)
    use_zbuffer = BoolProperty(name='Log', default=False)

    # Flag for float image
    is_float = BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image and get_active_ypaint_node()

    def draw(self, context):
        split = split_layout(self.layout, 0.5)

        split.prop(self, 'file_format', text='')
        row = split.row(align=True)
        row.prop(self, 'color_mode', expand=True)

        if self.file_format in {'PNG', 'JPEG2000', 'DPX', 'OPEN_EXR_MULTILAYER', 'OPEN_EXR', 'TIFF'}:
            row = self.layout.row()
            row.label(text='Color Depth:')
            row.prop(self, 'color_depth', expand=True)

        if self.file_format == 'PNG':
            self.layout.prop(self, 'compression')

        if self.file_format in {'JPEG', 'JPEG2000', 'WEBP'}:
            self.layout.prop(self, 'quality')

        if self.file_format == 'TIFF':
            self.layout.prop(self, 'tiff_codec')

        if self.file_format in {'OPEN_EXR', 'OPEN_EXR_MULTILAYER'}:
            self.layout.prop(self, 'exr_codec')

        if self.file_format == 'OPEN_EXR':
            self.layout.prop(self, 'use_zbuffer')

        if self.file_format == 'CINEON':
            self.layout.label('Hard coded Non-Linear, Gamma:1.7')

        if self.file_format == 'JPEG2000':
            self.layout.prop(self, 'jpeg2k_codec')
            row = self.layout.row()
            row.prop(self, 'use_jpeg2k_cinema_48')
            row.prop(self, 'use_jpeg2k_cinema_preset')
            self.layout.prop(self, 'use_jpeg2k_ycc')

        if self.file_format == 'DPX':
            self.layout.prop(self, 'use_cineon_log')

        self.layout.prop(self, 'copy')
        if not self.copy:
            self.layout.prop(self, 'relative')

    def invoke(self, context, event):
        self.use_filter_image = True

        file_ext = format_extensions[self.file_format]
        filename = bpy.path.basename(context.image.filepath)

        # Set filepath
        if context.image.filepath == '' or filename == '' or '.<UDIM>.' in filename:
            yp = get_active_ypaint_node().node_tree.yp

            name = context.image.name
            name += '.<UDIM>' if '.<UDIM>.' in filename else ''

            # Remove addon title from the file names
            if yp.use_baked and name.startswith(get_addon_title() + ' '):
                name = name.replace(get_addon_title() + ' ', '')

            if not name.endswith(file_ext): name += file_ext
            self.filepath = name
        else:
            self.filepath = context.image.filepath

        # Pass context.image to self
        self.image = context.image

        if self.image.yia.is_image_atlas:
            return self.execute(context)

        # Set default color mode 
        if self.file_format in {'BMP', 'JPEG', 'CINEON', 'HDR'}:
            self.color_mode = 'RGB'
        else: self.color_mode = 'RGBA'

        if self.image.is_float:
            self.is_float = True
            #self.file_format = 'OPEN_EXR'
            #if self.file_format in {'PNG', 'JPEG2000'}:
            if self.color_depth == '8':
                self.color_depth = '16'
        else:
            self.is_float = False

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def check(self, context):
        change_ext = False
        filepath = self.filepath
        file_ext = format_extensions[self.file_format]

        if bpy.path.basename(filepath):

            # Check current extensions
            for form, ext in format_extensions.items():
                if filepath.endswith(ext):
                    filepath = filepath.replace(ext, '')
                    break

            filepath = bpy.path.ensure_ext(filepath, file_ext)

            if filepath != self.filepath:
                self.filepath = filepath
                change_ext = True  

        return change_ext
        #return True

    def unpack_image(self, context):
        image = self.image

        # Get blender default unpack directory
        self.default_dir = os.path.join(os.path.abspath(bpy.path.abspath('//')), 'textures')

        # Check if default directory is available or not, delete later if not found now
        self.default_dir_found = os.path.isdir(self.default_dir)

        # Blender always unpack at \\textures\file.ext
        if image.filepath == '':
            self.default_filepath = os.path.join(self.default_dir, image.name)
        else: self.default_filepath = os.path.join(self.default_dir, bpy.path.basename(image.filepath))

        # Check if file with default path is already available
        self.temp_path = ''
        if os.path.isfile(self.default_filepath) and self.default_filepath != self.filepath:
            self.temp_path = os.path.join(self.default_dir, '__TEMP__')
            os.rename(self.default_filepath, self.temp_path)

        # Unpack the file
        image.unpack()
        self.unpacked_path = bpy.path.abspath(image.filepath)

        # HACK: Unpacked path sometimes has inconsistent backslash
        folder, file = os.path.split(self.unpacked_path)
        self.unpacked_path = os.path.join(folder, file)

    def remove_unpacked_image(self, context):
        image = self.image

        # Remove unpacked file
        if self.filepath != self.unpacked_path:
            if image.source == 'TILED':
                for tile in image.tiles:
                    unpacked_path = self.unpacked_path.replace('<UDIM>', str(tile.number))
                    try: os.remove(unpacked_path)
                    except Exception as e: print(e)
            else:
                os.remove(self.unpacked_path)

        # Rename back temporary file
        if self.temp_path != '':
            if self.temp_path != self.filepath:
                os.rename(self.temp_path, self.default_filepath)
            else: os.remove(self.temp_path)

        # Delete default directory if not found before
        if not self.default_dir_found:
            os.rmdir(self.default_dir)

    def execute(self, context):
        image = self.image

        if image.yia.is_image_atlas:
            self.report({'ERROR'}, 'Unpacking image atlas is not supported yet!')
            return {'CANCELLED'}

        if self.copy:
            image = self.image = duplicate_image(image, ondisk_duplicate=False)

        # Need to pack first to save the image
        if image.is_dirty:
            if is_bl_newer_than(2, 80):
                image.pack()
            else:
                if image.is_float:
                    pack_float_image(image)
                else: image.pack(as_png=True)

        # Unpack image if image is packed (Only necessary for Blender 2.80 and lower)
        # Packing and unpacking sometimes does not work if the blend file is not saved yet
        unpacked_to_disk = False
        if not is_bl_newer_than(2, 81) and bpy.data.filepath != '' and image.packed_file:
            unpacked_to_disk = True
            self.unpack_image(context)

        # Some image need to set to srgb when saving
        ori_colorspace = image.colorspace_settings.name
        if not image.is_float and not image.is_dirty:
            image.colorspace_settings.name = get_srgb_name()

        # Save image
        if image.source == 'TILED':
            override = bpy.context.copy()
            override['edit_image'] = image
            if is_bl_newer_than(4):
                with bpy.context.temp_override(**override):
                    bpy.ops.image.save_as(copy=self.copy, filepath=self.filepath, relative_path=self.relative)
            else: bpy.ops.image.save_as(override, copy=self.copy, filepath=self.filepath, relative_path=self.relative)
        else:
            # Create temporary scene
            tmpscene = bpy.data.scenes.new('Temp Save As Scene')

            # Blender 2.80 has filmic as default color settings, change it to standard
            if is_bl_newer_than(2, 80):
                tmpscene.view_settings.view_transform = 'Standard'

            # Set settings
            settings = tmpscene.render.image_settings
            settings.file_format = self.file_format
            settings.color_mode = self.color_mode
            settings.color_depth = self.color_depth
            settings.compression = self.compression
            settings.quality = self.quality
            if hasattr(settings, 'tiff_codec'): settings.tiff_codec = self.tiff_codec
            settings.exr_codec = self.exr_codec
            settings.jpeg2k_codec = self.jpeg2k_codec
            settings.use_jpeg2k_cinema_48 = self.use_jpeg2k_cinema_48
            settings.use_jpeg2k_cinema_preset = self.use_jpeg2k_cinema_preset
            settings.use_jpeg2k_ycc = self.use_jpeg2k_ycc
            settings.use_cineon_log = self.use_cineon_log
            if hasattr(settings, 'use_zbuffer'): settings.use_zbuffer = self.use_zbuffer

            image.save_render(self.filepath, scene=tmpscene)

            if not self.copy:
                image.filepath = self.filepath

                if self.relative and bpy.data.filepath != '':
                    try: image.filepath = bpy.path.relpath(image.filepath)
                    except Exception as e: print(e)
                else: image.filepath = bpy.path.abspath(image.filepath)

                image.source = 'FILE'
                image.reload()

            # Delete temporary scene
            remove_datablock(bpy.data.scenes, tmpscene)

        # Remove unpacked file
        if unpacked_to_disk:
            self.remove_unpacked_image(context)

        # Remove packed flag
        if is_bl_newer_than(2, 81) and image.packed_file:
            image.unpack(method='REMOVE')

        # Set back colorspace settings
        if image.colorspace_settings.name != ori_colorspace:
            image.colorspace_settings.name = ori_colorspace

        # Delete copied image
        if self.copy:
            remove_datablock(bpy.data.images, image)

        return {'FINISHED'}

class YSavePackAll(bpy.types.Operator):
    """Save and Pack All Image Layers"""
    bl_idname = "wm.y_save_pack_all"
    bl_label = "Save and Pack All Image Layers"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):
        ypui = bpy.context.window_manager.ypui
        #T = time.time()
        yp = get_active_ypaint_node().node_tree.yp
        save_pack_all(yp)
        #print('INFO:', 'All images are saved/packed in', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        ypui.refresh_image_hack = False
        return {'FINISHED'}

def toggle_image_bit_depth(image, no_copy=False, force_srgb=False):

    if image.yua.is_udim_atlas or image.yia.is_image_atlas:
        self.report({'ERROR'}, 'Cannot convert image atlas segment to different bit depth!')
        return {'CANCELLED'}

    # Create new image based on original image but with different bit depth
    if image.source == 'TILED':

        # Make sure image has filepath
        if image.filepath == '': UDIM.initial_pack_udim(image)

        tilenums = [tile.number for tile in image.tiles]
        new_image = bpy.data.images.new(
            image.name, width=image.size[0], height=image.size[1], 
            alpha=True, float_buffer=not image.is_float, tiled=True
        )

        # Fill tiles
        color = (0, 0, 0, 0)
        for tilenum in tilenums:
            ori_width = image.tiles.get(tilenum).size[0]
            ori_height = image.tiles.get(tilenum).size[1]
            UDIM.fill_tile(new_image, tilenum, color, ori_width, ori_height)
        UDIM.initial_pack_udim(new_image, color)

    else:
        new_image = bpy.data.images.new(
            image.name, width=image.size[0], height=image.size[1], 
            alpha=True, float_buffer=not image.is_float
        )

        if image.filepath != '':
            new_image.filepath = image.filepath

    if force_srgb:
        new_image.colorspace_settings.name = get_srgb_name()
    else: new_image.colorspace_settings.name = image.colorspace_settings.name

    # Copy image pixels
    if no_copy == False:
        if image.source == 'TILED':
            UDIM.copy_udim_pixels(image, new_image)
        else: copy_image_pixels(image, new_image)

    # Pack image
    if image.packed_file and image.source != 'TILED':
        if is_bl_newer_than(2, 80):
            new_image.pack()
        else:
            if new_image.is_float:
                pack_float_image(new_image)
            else: new_image.pack(as_png=True)

        # HACK: Float image need to be reloaded after packing to be showed correctly
        if new_image.is_float:
            new_image.reload()

    # Replace image
    replace_image(image, new_image)

    return new_image

class YConvertImageBitDepth(bpy.types.Operator):
    """Convert Image Bit Depth"""
    bl_idname = "image.y_convert_image_bit_depth"
    bl_label = "Convert Image Bit Depth"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image

    def execute(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        image = context.image
        toggle_image_bit_depth(image)

        # Update image editor by setting active layer index
        yp.active_layer_index = yp.active_layer_index

        return {'FINISHED'}

def register():
    bpy.utils.register_class(YCopyImagePathToClipboard)
    bpy.utils.register_class(YOpenContainingImageFolder)
    bpy.utils.register_class(YInvertImage)
    bpy.utils.register_class(YRefreshImage)
    bpy.utils.register_class(YPackImage)
    bpy.utils.register_class(YSaveImage)
    bpy.utils.register_class(YSaveAsImage)
    bpy.utils.register_class(YSavePackAll)
    bpy.utils.register_class(YSaveAllBakedImages)
    bpy.utils.register_class(YConvertImageBitDepth)

def unregister():
    bpy.utils.unregister_class(YCopyImagePathToClipboard)
    bpy.utils.unregister_class(YOpenContainingImageFolder)
    bpy.utils.unregister_class(YInvertImage)
    bpy.utils.unregister_class(YRefreshImage)
    bpy.utils.unregister_class(YPackImage)
    bpy.utils.unregister_class(YSaveImage)
    bpy.utils.unregister_class(YSaveAsImage)
    bpy.utils.unregister_class(YSavePackAll)
    bpy.utils.unregister_class(YSaveAllBakedImages)
    bpy.utils.unregister_class(YConvertImageBitDepth)
