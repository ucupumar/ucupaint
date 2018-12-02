import bpy, re
from bpy.props import *
from .subtree import *
#from . import Layer

def update_layer_channel_blur(self, context):
    yp = self.id_data.yp
    path = self.path_from_id()

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', path)
    if not m: return
    layer = yp.layers[int(m.group(1))]

    if self.enable_blur:
        enable_layer_source_tree(layer)
    else: disable_layer_source_tree(layer)

#class YLayerBlurSample(bpy.types.PropertyGroup):
#    pass

class YLayerBlur(bpy.types.PropertyGroup):

    #use_noise = BoolProperty(default=False)

    num_samples = EnumProperty(
            name='Samples',
            description='Blur Samples',
            items = (('8', '8', ''),
                     ('16', '16', ''),
                     ('32', '32', '')),
            default='16'
            )

    #samples = CollectionProperty(type=YLayerBlurSample)

    tree = PointerProperty(type=bpy.types.ShaderNodeTree)
    node = StringProperty(default='')

def register():
    bpy.utils.register_class(YLayerBlur)

def unregister():
    bpy.utils.unregister_class(YLayerBlur)
