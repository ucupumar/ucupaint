import bpy, re
from bpy.props import *
from .subtree import *
#from . import Layer

def update_tex_channel_blur(self, context):
    tl = self.id_data.tl
    path = self.path_from_id()

    m = re.match(r'tl\.layers\[(\d+)\]\.channels\[(\d+)\]', path)
    if not m: return
    layer = tl.layers[int(m.group(1))]

    if self.enable_blur:
        enable_tex_source_tree(layer)
    else: disable_tex_source_tree(layer)

#class YTextureBlurSample(bpy.types.PropertyGroup):
#    pass

class YTextureBlur(bpy.types.PropertyGroup):

    #use_noise = BoolProperty(default=False)

    num_samples = EnumProperty(
            name='Samples',
            description='Blur Samples',
            items = (('8', '8', ''),
                     ('16', '16', ''),
                     ('32', '32', '')),
            default='16'
            )

    #samples = CollectionProperty(type=YTextureBlurSample)

    tree = PointerProperty(type=bpy.types.ShaderNodeTree)
    node = StringProperty(default='')

def register():
    bpy.utils.register_class(YTextureBlur)

def unregister():
    bpy.utils.unregister_class(YTextureBlur)
