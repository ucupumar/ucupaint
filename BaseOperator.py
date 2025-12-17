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

def image_size_items(self, context):
    ypup = get_user_preferences()

    items = []

    for option in ypup.image_size_options:
        items.append((option.name, option.name, ''))

    return items

def default_image_size():
    #ypup = get_user_preferences()

    # HACK: Load default image size setting from file 
    # since user preference is not accesible in this scope
    index = get_image_option_index_from_file()

    # NOTE: Index 1 is the default since `1024` option has index of 1
    return index if index != None else 1

class NewImage():
    image_size : EnumProperty(
        name = 'Image Size',
        description = 'Image size',
        items = image_size_items,
        default = default_image_size(),
        #update = update_image_size_options
    )

    def invoke_operator(self, context, event):
        ypup = get_user_preferences()

        # Force to set the image size if image size option is changed during blender session
        if ypup.ori_default_image_size_option != ypup.default_image_size_option and ypup.default_image_size_option < len(ypup.image_size_options):
            self.image_size = [opt.name for i, opt in enumerate(ypup.image_size_options) if i == ypup.default_image_size_option][0]

