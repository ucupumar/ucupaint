import bpy
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
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
