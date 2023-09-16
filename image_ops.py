import bpy, shutil, os
import tempfile
from bpy.props import *
from bpy_extras.io_utils import ExportHelper
#from bpy_extras.image_utils import load_image  
from .common import *
import time

def save_float_image(image):
    original_path = image.filepath

    # Create temporary scene
    tmpscene = bpy.data.scenes.new('Temp Scene')

    # Set settings
    settings = tmpscene.render.image_settings

    # Check current extensions
    for form, ext in format_extensions.items():
        if image.filepath.endswith(ext):
            settings.file_format = form
            break
    
    if settings.file_format in {'OPEN_EXR', 'OPEN_EXR_MULTILAYER'}:
        settings.exr_codec = 'ZIP'

    #ori_colorspace = image.colorspace_settings.name
    full_path = bpy.path.abspath(image.filepath)
    image.save_render(full_path, scene=tmpscene)
    image.source = 'FILE'

    # Delete temporary scene
    bpy.data.scenes.remove(tmpscene)

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
        image.colorspace_settings.name = 'sRGB'
    else: image.colorspace_settings.name = 'Non-Color'

    # Delete temporary scene
    bpy.data.scenes.remove(tmpscene)

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
                        if is_greater_than_280():
                            if not any([s for s in bpy.data.scenes if o.object.name in s.collection.all_objects]):
                                removed_references.append(o.object.name)
                                indices.append(i)
                        else:
                            if not any([s for s in bpy.data.scenes if o.object.name in s.objects]):
                                removed_references.append(o.object.name)
                                indices.append(i)

                for i in reversed(indices):
                    segment.bake_info.selected_objects.remove(i)

                # Check if other objects data are still accessible on any view layers
                indices = []
                for i, o in enumerate(segment.bake_info.other_objects):
                    if o.object:
                        if is_greater_than_280():
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
                    if is_greater_than_280():
                        if not any([s for s in bpy.data.scenes if o.object.name in s.collection.all_objects]):
                            removed_references.append(o.object.name)
                            indices.append(i)
                    else:
                        if not any([s for s in bpy.data.scenes if o.object.name in s.objects]):
                            removed_references.append(o.object.name)
                            indices.append(i)
            for i in reversed(indices):
                image.y_bake_info.selected_objects.remove(i)

            # Check if other objects data are still accessible on any view layers
            indices = []
            for i, o in enumerate(image.y_bake_info.other_objects):
                if o.object:
                    if is_greater_than_280():
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

def save_pack_all(yp, only_dirty = True):

    tree = yp.id_data

    images = []
    for layer in yp.layers:
        
        # Layer image
        if layer.type == 'IMAGE':
            source = get_layer_source(layer)
            if source.image and source.image not in images:
                images.append(source.image)

        # Mask image
        for mask in layer.masks:
            if mask.type == 'IMAGE':
                mask_tree = get_mask_tree(mask)
                source = mask_tree.nodes.get(mask.source)
                if source.image and source.image not in images:
                    images.append(source.image)

        # Channel override image
        for ch in layer.channels:

            if ch.override and ch.override_type == 'IMAGE':
                source = get_channel_source(ch, layer)
                if source.image and source.image not in images:
                    images.append(source.image)

            if ch.override_1 and ch.override_1_type == 'IMAGE':
                source = get_channel_source_1(ch, layer)
                if source.image and source.image not in images:
                    images.append(source.image)

    # Baked images
    for ch in yp.channels:
        baked = tree.nodes.get(ch.baked)
        if baked and baked.image and baked.image not in images:
            images.append(baked.image)

        if ch.type == 'NORMAL':
            baked_disp = tree.nodes.get(ch.baked_disp)
            if baked_disp and baked_disp.image and baked_disp.image not in images:
                images.append(baked_disp.image)

            if not is_overlay_normal_empty(yp):
                baked_normal_overlay = tree.nodes.get(ch.baked_normal_overlay)
                if baked_normal_overlay and baked_normal_overlay.image and baked_normal_overlay.image not in images:
                    images.append(baked_normal_overlay.image)

    packed_float_images = []

    #print()
    # Temporary scene for blender 3.30 hack
    tmpscene = None
    if is_greater_than_330():
        tmpscene = bpy.data.scenes.new('Temp Save Scene')
        tmpscene.view_settings.view_transform = 'Standard'
        tmpscene.render.image_settings.file_format = 'PNG'

    # Save/pack images
    for image in images:
        clean_object_references(image)
        if not image: continue
        if only_dirty and not image.is_dirty: continue
        T = time.time()
        if image.packed_file or image.filepath == '':
            if is_greater_than_280():
                image.pack()
            else:
                if image.is_float:
                    pack_float_image(image)
                    packed_float_images.append(image)
                else: 
                    image.pack(as_png=True)

            print('INFO:', image.name, 'image is packed at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        else:
            if image.is_float:
                save_float_image(image)
            else:
                # BLENDER BUG: Blender 3.3 has wrong srgb if not packed first
                if is_greater_than_330() and image.colorspace_settings.name in {'Linear', 'Non-Color'}:

                    # Get image path
                    path = bpy.path.abspath(image.filepath)

                    # Pack image first
                    image.pack()
                    image.colorspace_settings.name = 'sRGB'

                    # Remove old files to avoid caching (?)
                    try: os.remove(path)
                    except Exception as e: print(e)
                    
                    # Then unpack
                    default_dir, default_dir_found, default_filepath, temp_path, unpacked_path = unpack_image(image, path)

                    # Save image
                    image.save_render(path, scene=tmpscene)

                    # Set the filepath to the image
                    try: image.filepath = bpy.path.relpath(path)
                    except: image.filepath = path

                    # Bring back linear
                    image.colorspace_settings.name = 'Non-Color'

                    # Remove unpacked images on Blender 3.3 
                    remove_unpacked_image_path(image, path, default_dir, default_dir_found, default_filepath, temp_path, unpacked_path)

                    print('INFO:', image.name, 'image is saved at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

                else:
                    try:
                        ori_colorspace = image.colorspace_settings.name
                        image.save()
                        image.colorspace_settings.name = ori_colorspace

                        print('INFO:', image.name, 'image is saved at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
                    except Exception as e:
                        print(e)

    # Delete temporary scene
    if tmpscene:
        bpy.data.scenes.remove(tmpscene)

    # HACK: For some reason active float image will glitch after auto save
    # This is only happen if active object is on texture paint mode
    obj = bpy.context.object
    if len(yp.layers) > 0 and obj and obj.mode == 'TEXTURE_PAINT':
        layer = yp.layers[yp.active_layer_index]
        if layer.type == 'IMAGE':
            source = get_layer_source(layer)
            image = source.image
            if image in packed_float_images:
                ypui = bpy.context.window_manager.ypui
                ypui.refresh_image_hack = True

class YInvertImage(bpy.types.Operator):
    """Invert Image"""
    bl_idname = "node.y_invert_image"
    bl_label = "Invert Image"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image

    def execute(self, context):

        if context.image.yia.is_image_atlas:
            self.report({'ERROR'}, 'Cannot invert image atlas!')
            return {'CANCELLED'}

        if not is_greater_than_282():
            # Copy context
            override = bpy.context.copy()
            override['edit_image'] = context.image

            # Invert image
            #context.image.reload()
            # For some reason this no longer works since Blender 2.82
            bpy.ops.image.invert(override, invert_r=True, invert_g=True, invert_b=True)
        else:

            # Search for context
            override = None
            space = None
            ori_image = None

            #for screen in bpy.data.screens:
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    space = area.spaces[0]
                    ori_image = space.image
                    space.image = context.image

                    override = context.copy()

                    override['area'] = area
                    override['space_data'] = space
                    break

            if override:
                # Invert image
                bpy.ops.image.invert(override, invert_r=True, invert_g=True, invert_b=True)
                space.image = ori_image

                self.report({'INFO'}, 'You probably need to move the viewport to see the changes!')

            else:
                self.report({'ERROR'}, 'To use this feature, Image Editor should be opened anywhere on this screen!')
                return {'CANCELLED'}

        return {'FINISHED'}

class YRefreshImage(bpy.types.Operator):
    """Reload Image"""
    bl_idname = "node.y_reload_image"
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
    bl_idname = "node.y_pack_image"
    bl_label = "Pack Image"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image and not context.image.packed_file

    def execute(self, context):

        T = time.time()

        # Save file to temporary place first if image is float
        if is_greater_than_280():
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
                    if is_greater_than_280():
                        baked_disp.image.pack()
                    else:
                        if baked_disp.image.is_float:
                            pack_float_image(baked_disp.image)
                        else: baked_disp.image.pack(as_png=True)

                    baked_disp.image.filepath = ''

                if not is_overlay_normal_empty(yp):
                    baked_normal_overlay = tree.nodes.get(ch.baked_normal_overlay)
                    if baked_normal_overlay and baked_normal_overlay.image and not baked_normal_overlay.image.packed_file:
                        if is_greater_than_280():
                            baked_normal_overlay.image.pack()
                        else:
                            if baked_normal_overlay.image.is_float:
                                pack_float_image(baked_normal_overlay.image)
                            else: baked_normal_overlay.image.pack(as_png=True)

                    baked_normal_overlay.image.filepath = ''

        print('INFO:', context.image.name, 'image is packed at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

        return {'FINISHED'}

class YSaveImage(bpy.types.Operator):
    """Save Image"""
    bl_idname = "node.y_save_image"
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
        }

def color_mode_items(self, context):
    if self.file_format in {'BMP', 'JPEG', 'CINEON', 'HDR'}:
        items = (('BW', 'BW', ''),
                ('RGB', 'RGB', ''))
    else:
        items = (('BW', 'BW', ''),
                ('RGB', 'RGB', ''),
                ('RGBA', 'RGBA', ''))
    return items

def color_depth_items(self, context):
    if self.file_format in {'PNG', 'TIFF'}:
        items = (('8', '8', ''),
                ('16', '16', ''))
    elif self.file_format in {'JPEG2000'}:
        items = (('8', '8', ''),
                ('12', '12', ''),
                ('16', '16', ''))
    elif self.file_format in {'DPX'}:
        items = (('8', '8', ''),
                ('10', '10', ''),
                ('12', '12', ''),
                ('16', '16', ''))
    elif self.file_format in {'OPEN_EXR_MULTILAYER', 'OPEN_EXR'}:
        items = (('16', 'Float (Half)', ''),
                ('32', 'Float (Full)', ''))
    else:
        items = (('8', '8', ''),
                ('10', '10', ''),
                ('12', '12', ''),
                ('16', '16', ''),
                ('32', '32', ''))

    return items

def update_save_as_file_format(self, context):
    if self.file_format in {'BMP', 'JPEG', 'CINEON', 'HDR'}:
        self.color_mode = 'RGB'
    else: self.color_mode = 'RGBA'

    if self.file_format in {'BMP', 'IRIS', 'PNG', 'JPEG', 'JPEG2000', 'TARGA', 'TARGA_RAW' }:
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
    bl_idname = "node.y_save_all_baked_images"
    bl_label = "Save All Baked Images"
    bl_options = {'REGISTER', 'UNDO'}

    # Define this to tell 'fileselect_add' that we want a directoy
    directory : bpy.props.StringProperty(
        name="Outdir Path",
        description="Where I will save my stuff"
        # subtype='DIR_PATH' is not needed to specify the selection mode.
        # But this will be anyway a directory path.
        )

    remove_whitespaces : bpy.props.BoolProperty(
            name="Remove Whitespaces",
            description="Remove whitespaces from baked image names",
            default=False
            )

    def invoke(self, context, event):
        # Open browser, take reference to 'self' read the path to selected
        # file, put path in predetermined self fields.
        # See: https://docs.blender.org/api/current/bpy.types.WindowManager.html#bpy.types.WindowManager.fileselect_add
        context.window_manager.fileselect_add(self)
        # Tells Blender to hang on for the slow user input
        return {'RUNNING_MODAL'}

    def execute(self, context):

        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp

        tmpscene = bpy.data.scenes.new('Temp Save As Scene')
        settings = tmpscene.render.image_settings

        # Blender 2.80 has filmic as default color settings, change it to standard
        if is_greater_than_280():
            tmpscene.view_settings.view_transform = 'Standard'

        images = []

        height_root_ch = get_root_height_channel(yp)

        for ch in yp.channels:
            if ch.no_layer_using: continue

            baked = tree.nodes.get(ch.baked)
            if baked and baked.image:
                images.append(baked.image)

            if ch == height_root_ch:

                baked_disp = tree.nodes.get(ch.baked_disp)
                if baked_disp and baked_disp.image:
                    images.append(baked_disp.image)

                if not is_overlay_normal_empty(yp):
                    baked_normal_overlay = tree.nodes.get(ch.baked_normal_overlay)
                    if baked_normal_overlay and baked_normal_overlay.image:
                        images.append(baked_normal_overlay.image)

        for image in images:

            settings.file_format = 'PNG'
            if image.is_float:
                settings.file_format = 'OPEN_EXR'
                settings.exr_codec = 'ZIP'

            if image.filepath == '':
                image_name = image.name
                # Remove addon title from the file names
                if image_name.startswith(get_addon_title() + ' '):
                    image_name = image_name.replace(get_addon_title() + ' ', '')
                filename = image_name + format_extensions[settings.file_format]
            else:
                filename = bpy.path.basename(image.filepath)

                # Check current extensions
                for form, ext in format_extensions.items():
                    if filename.endswith(ext):
                        settings.file_format = form
                        break

            if self.remove_whitespaces:
                filename = filename.replace(' ', '')

            path = os.path.join(self.directory, filename)

            # Need to pack first to save the image
            if image.is_dirty:
                if is_greater_than_280():
                    image.pack()
                else:
                    if image.is_float:
                        pack_float_image(image)
                    else: image.pack(as_png=True)

            # Some image need to set to srgb when saving
            ori_colorspace = image.colorspace_settings.name
            if not image.is_float:
                image.colorspace_settings.name = 'sRGB'
            
            #settings.file_format = file_format

            # Check if image is packed
            unpack = False
            if image.packed_file:
                unpack = True
                default_dir, default_dir_found, default_filepath, temp_path, unpacked_path = unpack_image(image, path)

            # Save image
            image.save_render(path, scene=tmpscene)

            # Set the filepath to the image
            try: image.filepath = bpy.path.relpath(path)
            except: image.filepath = path

            # Set back colorspace settings
            image.colorspace_settings.name = ori_colorspace

            # Remove temporarily unpacked image
            if unpack:
                remove_unpacked_image_path(image, path, default_dir, default_dir_found, default_filepath, temp_path, unpacked_path)

            #print(path)

        # Delete temporary scene
        bpy.data.scenes.remove(tmpscene)

        #print("Selected dir: '" + self.directory + "'")

        return {'FINISHED'}

class YSaveAsImage(bpy.types.Operator, ExportHelper):
    """Save As Image"""
    bl_idname = "node.y_save_as_image"
    bl_label = "Save As Image"
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob : StringProperty(
            default="*.bmp;*.rgb;*.png;*.jpg;*.jp2;*.tga;*.cin;*.dpx;*.exr;*.hdr;*.tif",
            options={'HIDDEN'},
            maxlen=255,  # Max internal buffer length, longer would be clamped.
            )

    file_format : EnumProperty(
            name = 'File Format',
            items = (
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
                    ('TIFF', 'TIFF', '', 'IMAGE_DATA', 12),
                    ),
            default = 'PNG',
            update = update_save_as_file_format
            )

    # File browser filter
    filter_folder : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    display_type : EnumProperty(
            items = (('FILE_DEFAULTDISPLAY', 'Default', ''),
                     ('FILE_SHORTDISLPAY', 'Short List', ''),
                     ('FILE_LONGDISPLAY', 'Long List', ''),
                     ('FILE_IMGDISPLAY', 'Thumbnails', '')),
            default = 'FILE_IMGDISPLAY',
            options={'HIDDEN', 'SKIP_SAVE'})

    copy : BoolProperty(name='Copy',
            description = 'Create a new image file without modifying the current image in Blender',
            default = False)

    relative : BoolProperty(name='Relative Path',
            description = 'Select the file relative to the blend file',
            default = True)

    color_mode : EnumProperty(
            name = 'Color Mode',
            items = color_mode_items)

    color_depth : EnumProperty(
            name = 'Color Depth',
            items = color_depth_items)

    tiff_codec : EnumProperty(
            name = 'Compression',
            items = (
                ('NONE', 'None', ''),
                ('DEFLATE', 'Deflate', ''),
                ('LZW', 'LZW', ''),
                ('PACKBITS', 'Pack Bits', ''),
                ),
            default = 'DEFLATE'
            )

    exr_codec : EnumProperty(
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

    jpeg2k_codec : EnumProperty(
            name = 'Codec',
            items = (
                ('JP2', 'JP2', ''),
                ('J2K', 'J2K', ''),
                ),
            default = 'JP2'
            )

    compression : IntProperty(name='Compression', default=15, min=0, max=100, subtype='PERCENTAGE')
    quality : IntProperty(name='Quality', default=90, min=0, max=100, subtype='PERCENTAGE')

    use_jpeg2k_cinema_48 : BoolProperty(name='Cinema 48', default=False)
    use_jpeg2k_cinema_preset : BoolProperty(name='Cinema', default=False)
    use_jpeg2k_ycc : BoolProperty(name='YCC', default=False)
    use_cineon_log : BoolProperty(name='Log', default=False)
    use_zbuffer : BoolProperty(name='Log', default=False)

    # Option to unpack image if image is packed
    unpack : BoolProperty(default=False)

    # Flag for float image
    is_float : BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image and get_active_ypaint_node()

    def draw(self, context):
        if is_greater_than_280(): 
            split = self.layout.split(factor=0.5)
        else: split = self.layout.split(percentage=0.5)

        split.prop(self, 'file_format', text='')
        row = split.row(align=True)
        row.prop(self, 'color_mode', expand=True)

        if self.file_format in {'PNG', 'JPEG2000', 'DPX', 'OPEN_EXR_MULTILAYER', 'OPEN_EXR', 'TIFF'}:
            row = self.layout.row()
            row.label(text='Color Depth:')
            row.prop(self, 'color_depth', expand=True)

        if self.file_format == 'PNG':
            self.layout.prop(self, 'compression')

        if self.file_format in {'JPEG', 'JPEG2000'}:
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
        file_ext = format_extensions[self.file_format]

        # Set filepath
        if context.image.filepath == '':
            yp = get_active_ypaint_node().node_tree.yp

            name = context.image.name

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
            self.file_format = 'OPEN_EXR'
            if self.file_format in {'PNG', 'JPEG2000'}:
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

        # Need to pack first to save the image
        if image.is_dirty:
            if is_greater_than_280():
                image.pack()
            else:
                if image.is_float:
                    pack_float_image(image)
                else: image.pack(as_png=True)

        # Unpack image if image is packed
        unpack = False
        if self.unpack or image.packed_file:
            unpack = True
            self.unpack_image(context)

        # Create temporary scene
        tmpscene = bpy.data.scenes.new('Temp Save As Scene')

        # Blender 2.80 has filmic as default color settings, change it to standard
        if is_greater_than_280():
            tmpscene.view_settings.view_transform = 'Standard'

        # Some image need to set to srgb when saving
        ori_colorspace = image.colorspace_settings.name
        if not image.is_float:
            image.colorspace_settings.name = 'sRGB'

        # Set settings
        settings = tmpscene.render.image_settings
        settings.file_format = self.file_format
        settings.color_mode = self.color_mode
        settings.color_depth = self.color_depth
        settings.compression = self.compression
        settings.quality = self.quality
        settings.tiff_codec = self.tiff_codec
        settings.exr_codec = self.exr_codec
        settings.jpeg2k_codec = self.jpeg2k_codec
        settings.use_jpeg2k_cinema_48 = self.use_jpeg2k_cinema_48
        settings.use_jpeg2k_cinema_preset = self.use_jpeg2k_cinema_preset
        settings.use_jpeg2k_ycc = self.use_jpeg2k_ycc
        settings.use_cineon_log = self.use_cineon_log
        if hasattr(settings, 'use_zbuffer'): settings.use_zbuffer = self.use_zbuffer

        #print(self.file_format)

        # Save image
        if image.source == 'TILED':
            ori_ui_type = bpy.context.area.ui_type
            bpy.context.area.ui_type = 'IMAGE_EDITOR'
            bpy.context.space_data.image = image
            bpy.ops.image.save_as(copy=self.copy, filepath=self.filepath, relative_path=self.relative)
            bpy.context.area.ui_type = ori_ui_type
        else:
            image.save_render(self.filepath, scene=tmpscene)

            if not self.copy:
                image.filepath = self.filepath

                if self.relative:
                    image.filepath = bpy.path.relpath(image.filepath)
                else: image.filepath = bpy.path.abspath(image.filepath)

                image.source = 'FILE'
                image.reload()

        # Remove unpacked file
        if unpack:
            self.remove_unpacked_image(context)

        # Set back colorspace settings
        image.colorspace_settings.name = ori_colorspace

        # Delete temporary scene
        bpy.data.scenes.remove(tmpscene)

        #context.image.save()
        return {'FINISHED'}

class YSavePackAll(bpy.types.Operator):
    """Save and Pack All Image Layers"""
    bl_idname = "node.y_save_pack_all"
    bl_label = "Save and Pack All Image Layers"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):
        ypui = bpy.context.window_manager.ypui
        #T = time.time()
        yp = get_active_ypaint_node().node_tree.yp
        save_pack_all(yp, only_dirty=False)
        #print('INFO:', 'All images is saved/packed at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        ypui.refresh_image_hack = False
        return {'FINISHED'}

def register():
    bpy.utils.register_class(YInvertImage)
    bpy.utils.register_class(YRefreshImage)
    bpy.utils.register_class(YPackImage)
    bpy.utils.register_class(YSaveImage)
    bpy.utils.register_class(YSaveAsImage)
    bpy.utils.register_class(YSavePackAll)
    bpy.utils.register_class(YSaveAllBakedImages)

def unregister():
    bpy.utils.unregister_class(YInvertImage)
    bpy.utils.unregister_class(YRefreshImage)
    bpy.utils.unregister_class(YPackImage)
    bpy.utils.unregister_class(YSaveImage)
    bpy.utils.unregister_class(YSaveAsImage)
    bpy.utils.unregister_class(YSavePackAll)
    bpy.utils.unregister_class(YSaveAllBakedImages)
