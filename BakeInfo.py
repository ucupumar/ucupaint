import bpy
from .common import *
from bpy.props import *

class YBakeInfoOtherObject(bpy.types.PropertyGroup):
    object : PointerProperty(type=bpy.types.Object)

class YBakeInfoSelectedVertex(bpy.types.PropertyGroup):
    index : IntProperty(default=0)

class YBakeInfoSelectedObject(bpy.types.PropertyGroup):
    object : PointerProperty(type=bpy.types.Object)
    selected_vertex_indices : CollectionProperty(type=YBakeInfoSelectedVertex)

class YBakeInfoProps(bpy.types.PropertyGroup):

    is_baked : BoolProperty(default=False)

    bake_type : EnumProperty(
            name = 'Bake Type',
            description = 'Bake Type',
            items = bake_type_items,
            default='AO'
            )

    samples : IntProperty(name='Bake Samples', 
            description='Bake Samples, more means less jagged on generated textures', 
            default=1, min=1)

    margin : IntProperty(name='Bake Margin',
            description = 'Bake margin in pixels',
            default=5, min=0, subtype='PIXEL')

    flip_normals : BoolProperty(
            name='Flip Normals',
            description='Flip normal of mesh',
            default=False
            )
    
    only_local : BoolProperty(
            name='Only Local',
            description='Only bake local ambient occlusion',
            default=False
            )

    subsurf_influence : BoolProperty(
            name='Subsurf Influence',
            description='Take account subsurf when baking cavity',
            default=False
            )
    
    force_bake_all_polygons : BoolProperty(
            name='Force Bake all Polygons',
            description='Force bake all polygons, useful if material is not using direct polygon (ex: solidify material)',
            default=False)

    fxaa : BoolProperty(name='Use FXAA', 
            description = "Use FXAA to baked image (doesn't work with float images)",
            default=False)

    ssaa : BoolProperty(name='Use SSAA', 
            description = "Use Supersample AA to baked image",
            default=False)

    use_baked_disp : BoolProperty(
            name='Use Baked Displacement Map',
            description='Use baked displacement map, this will also apply subdiv setup on object',
            default=False
            )

    bake_device : EnumProperty(
            name='Bake Device',
            description='Device to use for baking',
            items = (('GPU', 'GPU Compute', ''),
                     ('CPU', 'CPU', '')),
            default='CPU'
            )

    cage_extrusion : FloatProperty(
            name = 'Cage Extrusion',
            description = 'Inflate the active object by the specified distance for baking. This helps matching to points nearer to the outside of the selected object meshes',
            default=0.2, min=0.0, max=1.0)

    max_ray_distance : FloatProperty(
            name = 'Max Ray Distance',
            description = 'The maximum ray distance for matching points between the active and selected objects. If zero, there is no limit',
            default=0.2, min=0.0, max=1.0)

    # To store other objects info
    other_objects : CollectionProperty(type=YBakeInfoOtherObject)
    
    multires_base : IntProperty(default=1, min=0, max=16)

    hdr : BoolProperty(name='32 bit Float', default=False)

    # AO Props
    ao_distance : FloatProperty(default=1.0)

    # Bevel Props
    bevel_samples : IntProperty(default=4, min=2, max=16)
    bevel_radius : FloatProperty(default=0.05, min=0.0, max=1000.0)

    use_image_atlas : BoolProperty(
            name = 'Use Image Atlas',
            description='Use Image Atlas',
            default=False)

    selected_face_mode : BoolProperty(default=False)
    selected_objects : CollectionProperty(type=YBakeInfoSelectedObject)

def register():
    bpy.utils.register_class(YBakeInfoOtherObject)
    bpy.utils.register_class(YBakeInfoSelectedVertex)
    bpy.utils.register_class(YBakeInfoSelectedObject)
    bpy.utils.register_class(YBakeInfoProps)

    bpy.types.Image.y_bake_info = PointerProperty(type=YBakeInfoProps)

def unregister():
    bpy.utils.unregister_class(YBakeInfoOtherObject)
    bpy.utils.unregister_class(YBakeInfoSelectedVertex)
    bpy.utils.unregister_class(YBakeInfoSelectedObject)
    bpy.utils.unregister_class(YBakeInfoProps)

