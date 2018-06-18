import bpy, shutil, os
import tempfile
from bpy.props import *
from bpy_extras.io_utils import ExportHelper
#from bpy_extras.image_utils import load_image  
from .common import *
import time

def pack_float_image(image):
    original_path = image.filepath

    # Create temporary scene
    tmpscene = bpy.data.scenes.new('Temp Scene')

    # Set settings
    settings = tmpscene.render.image_settings

    #if image.filepath == '':
    #if original_path == '':
    if bpy.path.basename(original_path) == '':
        if image.use_alpha:
            settings.file_format = 'PNG'
            settings.color_depth = '16'
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
    image.save_render(temp_filepath, tmpscene)
    image.source = 'FILE'
    image.filepath = temp_filepath
    if image.file_format == 'PNG':
        image.colorspace_settings.name = 'sRGB'
    else: image.colorspace_settings.name = 'Linear'

    # Delete temporary scene
    bpy.data.scenes.remove(tmpscene)

    # Pack image
    image.pack()

    #image.reload()

    # Bring back to original path
    image.filepath = original_path
    os.remove(temp_filepath)

def save_pack_all(tl, only_dirty = True):

    packed_float_images = []
    for tex in tl.textures:
        T = time.time()
        if tex.type != 'IMAGE': continue
        source = tex.tree.nodes.get(tex.source)
        image = source.image
        if only_dirty and not image.is_dirty: continue
        if image.packed_file or image.filepath == '':
            if image.is_float:
                pack_float_image(image)
                packed_float_images.append(image)
            else: 
                image.pack(as_png=True)

            print('INFO:', image.name, 'image is packed at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        else:
            image.save()
            print('INFO:', image.name, 'image is saved at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

    # HACK: For some reason active float image will glitch after auto save
    # This is only happen if active object is on texture paint mode
    obj = bpy.context.object
    if len(tl.textures) > 0 and obj and obj.mode == 'TEXTURE_PAINT':
        tex = tl.textures[tl.active_texture_index]
        if tex.type == 'IMAGE':
            source = tex.tree.nodes.get(tex.source)
            image = source.image
            if image in packed_float_images:
                tlui = bpy.context.window_manager.tlui
                tlui.refresh_image_hack = True

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
        return hasattr(context, 'image') and context.image

    def execute(self, context):

        T = time.time()

        # Save file to temporary place first if image is float
        if context.image.is_float:
            pack_float_image(context.image)
        else: context.image.pack(as_png=True)

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
        context.image.save()
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

class YSaveAsImage(bpy.types.Operator, ExportHelper):
    """Save As Image"""
    bl_idname = "node.y_save_as_image"
    bl_label = "Save As Image"
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob = StringProperty(
            default="*.bmp;*.rgb;*.png;*.jpg;*.jp2;*.tga;*.cin;*.dpx;*.exr;*.hdr;*.tif",
            options={'HIDDEN'},
            maxlen=255,  # Max internal buffer length, longer would be clamped.
            )

    file_format = EnumProperty(
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
    filter_folder = BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image = BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    display_type = EnumProperty(
            items = (('FILE_DEFAULTDISPLAY', 'Default', ''),
                     ('FILE_SHORTDISLPAY', 'Short List', ''),
                     ('FILE_LONGDISPLAY', 'Long List', ''),
                     ('FILE_IMGDISPLAY', 'Thumbnails', '')),
            default = 'FILE_IMGDISPLAY',
            options={'HIDDEN', 'SKIP_SAVE'})

    copy = BoolProperty(name='Copy',
            description = 'Create a new image file without modifying the current image in Blender',
            default = False)

    relative = BoolProperty(name='Relative Path',
            description = 'Select the file relative to the blend file',
            default = True)

    color_mode = EnumProperty(
            name = 'Color Mode',
            items = color_mode_items)

    color_depth = EnumProperty(
            name = 'Color Depth',
            items = color_depth_items)

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

    # Option to unpack image if image is packed
    unpack = BoolProperty(default=False)

    # Flag for float image
    is_float = BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image

    def draw(self, context):
        split = self.layout.split(percentage=0.5)
        split.prop(self, 'file_format', text='')
        row = split.row(align=True)
        row.prop(self, 'color_mode', expand=True)

        if self.file_format in {'PNG', 'JPEG2000', 'DPX', 'OPEN_EXR_MULTILAYER', 'OPEN_EXR', 'TIFF'}:
            row = self.layout.row()
            row.label('Color Depth:')
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
            name = context.image.name
            if not name.endswith(file_ext): name += file_ext
            self.filepath = name
        else:
            self.filepath = context.image.filepath

        # Pass context.image to self
        self.image = context.image

        # Set default color mode 
        if self.file_format in {'BMP', 'JPEG', 'CINEON', 'HDR'}:
            self.color_mode = 'RGB'
        else: self.color_mode = 'RGBA'

        if self.image.is_float:
            self.is_float = True
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

    def remove_unpacked_image(self, context):

        # Remove unpacked file
        if self.filepath != self.unpacked_path:
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

        # Unpack image if image is packed
        unpack = False
        if self.unpack and image.packed_file:
            unpack = True
            self.unpack_image(context)

        # Create temporary scene
        tmpscene = bpy.data.scenes.new('Temp Scene')

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
        settings.use_zbuffer = self.use_zbuffer

        # Save image
        image.save_render(self.filepath, tmpscene)

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

        # Delete temporary scene
        bpy.data.scenes.remove(tmpscene)

        #context.image.save()
        return {'FINISHED'}

class YSavePackAll(bpy.types.Operator):
    """Save and Pack All Image Textures"""
    bl_idname = "node.y_save_pack_all"
    bl_label = "Save and Pack All Textures"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_texture_layers_node()

    def execute(self, context):
        tlui = bpy.context.window_manager.tlui
        #T = time.time()
        tl = get_active_texture_layers_node().node_tree.tl
        save_pack_all(tl, only_dirty=False)
        #print('INFO:', 'All images is saved/packed at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        tlui.refresh_image_hack = False
        return {'FINISHED'}
