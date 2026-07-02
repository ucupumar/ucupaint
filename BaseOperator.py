import bpy
from bpy.props import *
from .common import *

class FileSelectOptions():
    # File browser filter
    filter_folder : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})

    display_type : EnumProperty(
        items = (
            ('FILE_DEFAULTDISPLAY', 'Default', ''),
            ('FILE_SHORTDISLPAY', 'Short List', ''),
            ('FILE_LONGDISPLAY', 'Long List', ''),
            ('FILE_IMGDISPLAY', 'Thumbnails', '')
        ),
        default = 'FILE_IMGDISPLAY',
        options = {'HIDDEN', 'SKIP_SAVE'}
    )

class BlendMethodOptions():
    blend_method : EnumProperty(
        name = 'Blend Method', 
        description = 'Blend method for transparent material',
        items = (
            ('CLIP', 'Alpha Clip', ''),
            ('HASHED', 'Alpha Hashed', ''),
            ('BLEND', 'Alpha Blend', '')
        ),
        default = 'HASHED'
    )

    shadow_method : EnumProperty(
        name = 'Shadow Method', 
        description = 'Shadow method for transparent material',
        items = (
            ('CLIP', 'Alpha Clip', ''),
            ('HASHED', 'Alpha Hashed', ''),
        ),
        default = 'HASHED'
    )

    surface_render_method : EnumProperty(
        name = 'Surface Render Method', 
        description = 'Surface render method for transparent material',
        items = (
            ('DITHERED', 'Dithered', ''),
            ('BLENDED', 'Blended', ''),
        ),
        default = 'DITHERED'
    )

class OpenImage(FileSelectOptions):

    # File related
    files : CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory : StringProperty(maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'}) 

    relative : BoolProperty(name="Relative Path", default=True, description="Apply relative paths")

    def running_fileselect_modal(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def check(self, context):
        return True

    def generate_paths(self):
        return (fn.name for fn in self.files), self.directory

    def get_loaded_images(self):
        import_list, directory = self.generate_paths()
        loaded_images = tuple(load_image(path, directory) for path in import_list)

        return loaded_images

def channel_items_base(self, context):
    from . import lib

    items = []

    node = get_active_ypaint_node()
    if node:
        yp = node.node_tree.yp
        for i, ch in enumerate(yp.channels):
            # Add two spaces to prevent text from being translated
            text_ch_name = ch.name + '  '
            icon_name = lib.channel_custom_icon_dict[ch.type]
            items.append((str(i), text_ch_name, '', lib.get_icon(icon_name), i))

    return items

def channel_items(self, context):
    from . import lib

    items = channel_items_base(self, context)
    items.append(('-1', 'All Channels', '', lib.get_icon('channels'), len(items)))

    return items

def is_self_channel_idx_accessible(self):
    # NOTE: Check if self.channel_idx is accessible or not since Blender Debug build always returns invalid pointer
    try:
        channel_idx = int(self.channel_idx)
        return True
    except: pass

    return False

def get_self_channel_idx(self):
    # NOTE: This function is workaround for Blender Debug build since it always returns invalid pointer from self.channel_idx
    try: return int(self.channel_idx)
    except Exception as e:
        ypup = get_user_preferences()
        if ypup.developer_mode: print('EXCEPTIION:', e)

    return 0

def draw_self_channel_idx(self, layout, yp=None):
    if is_self_channel_idx_accessible(self):
        layout.prop(self, 'channel_idx', text='')
    else:
        if yp == None:
            node = get_active_ypaint_node()
            yp = node.node_tree.yp if node else None

        if yp and len(yp.channels) > 0:
            from . import lib

            first_ch = yp.channels[0]
            icon_name = lib.channel_custom_icon_dict[first_ch.type]
            layout.label(text=first_ch.name, icon_value=lib.get_icon(icon_name))

