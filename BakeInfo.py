import bpy
from .common import *
from bpy.props import *

class YBakeInfoOtherObject(bpy.types.PropertyGroup):
    if is_bl_newer_than(2, 79):
        object = PointerProperty(type=bpy.types.Object)
    object_name = StringProperty(default='')

class YBakeInfoSelectedVertex(bpy.types.PropertyGroup):
    index = IntProperty(default=0)

class YBakeInfoSelectedObject(bpy.types.PropertyGroup):
    if is_bl_newer_than(2, 79):
        object = PointerProperty(type=bpy.types.Object)
    object_name = StringProperty(default='')

    selected_vertex_indices = CollectionProperty(type=YBakeInfoSelectedVertex)

class YBakeInfoProps(bpy.types.PropertyGroup):
    is_baked = BoolProperty(default=False) # Flag to mark if the image is from baking or not
    is_baked_channel = BoolProperty(default=False) # Flag to mark if the image baked from main channel
    is_baked_entity = BoolProperty(default=False) # Flag to mark if the image baked from entity

    bake_type = EnumProperty(
        name = 'Bake Type',
        description = 'Bake Type',
        items = bake_type_items,
        default = 'AO'
    )

    baked_entity_type = StringProperty(
        name = 'Baked Entity Type',
        description = 'Baked entity type',
        default = ''
    )

    samples = IntProperty(
        name = 'Bake Samples', 
        description = 'Bake Samples, more means less jagged on generated textures', 
        default=1, min=1
    )

    margin = IntProperty(
        name = 'Bake Margin',
        description = 'Bake margin in pixels',
        subtype = 'PIXEL',
        default=5, min=0
    )

    margin_type = EnumProperty(
        name = 'Margin Type',
        description = '',
        items = (
            ('ADJACENT_FACES', 'Adjacent Faces', 'Use pixels from adjacent faces across UV seams.'),
            ('EXTEND', 'Extend', 'Extend border pixels outwards')
        ),
        default = 'ADJACENT_FACES'
    )

    flip_normals = BoolProperty(
        name = 'Flip Normals',
        description = 'Flip normal of mesh',
        default = False
    )
    
    only_local = BoolProperty(
        name = 'Only Local',
        description = 'Only bake local ambient occlusion',
        default = False
    )

    subsurf_influence = BoolProperty(
        name = 'Subsurf Influence',
        description = 'Take account subsurf when baking cavity',
        default = False
    )
    
    force_bake_all_polygons = BoolProperty(
        name = 'Force Bake all Polygons',
        description = 'Force bake all polygons, useful if material is not using direct polygon (ex: solidify material)',
        default = False
    )

    fxaa = BoolProperty(
        name='Use FXAA', 
        description = "Use FXAA on baked image (doesn't work with float images)",
        default = False
    )

    ssaa = BoolProperty(
        name = 'Use SSAA', 
        description = "Use Supersample AA on baked image",
        default = False
    )

    denoise = BoolProperty(
        name = 'Use Denoise', 
        description = "Use Denoise on baked image",
        default = True
    )

    blur = BoolProperty(
        name = 'Use Blur', 
        description = "Use blur to baked image",
        default = False
    )

    blur_factor = FloatProperty(
        name = 'Blur Factor',
        description = "Blur factor to baked image",
        default=1.0, min=0.0, max=100.0
    )

    use_baked_disp = BoolProperty(
        name = 'Use Baked Displacement Map',
        description = 'Use baked displacement map, this will also apply subdiv setup on object',
        default = False
    )

    bake_device = EnumProperty(
        name = 'Bake Device',
        description = 'Device to use for baking',
        items = (
            ('GPU', 'GPU Compute', ''),
            ('CPU', 'CPU', '')
        ),
        default = 'CPU'
    )

    cage_object_name = StringProperty(
        name = 'Cage Object',
        description = 'Object to use as cage instead of calculating the cage from the active object with cage extrusion',
        default = ''
    )

    cage_extrusion = FloatProperty(
        name = 'Cage Extrusion',
        description = 'Inflate the active object by the specified distance for baking. This helps matching to points nearer to the outside of the selected object meshes',
        default=0.2, min=0.0, max=1.0
    )

    max_ray_distance = FloatProperty(
        name = 'Max Ray Distance',
        description = 'The maximum ray distance for matching points between the active and selected objects. If zero, there is no limit',
        default=0.2, min=0.0, max=1.0
    )

    use_udim = BoolProperty(
        name = 'Use UDIM Tiles',
        description = 'Use UDIM Tiles',
        default = False
    )

    aa_level = IntProperty(
        name = 'Anti Aliasing Level',
        description = 'Super Sample Anti Aliasing Level (1=off)',
        default=1, min=1, max=2
    )

    interpolation = EnumProperty(
        name = 'Image Interpolation Type',
        description = 'Image interpolation type',
        items = interpolation_type_items,
        default = 'Linear'
    )

    use_float_for_normal = BoolProperty(
        name = 'Use Float for Normal',
        description = 'Use float image for baked normal',
        default = False
    )

    use_float_for_displacement = BoolProperty(
        name = 'Use Float for Displacement',
        description = 'Use float image for baked displacement',
        default = False
    )

    use_osl = BoolProperty(
        name = 'Use OSL',
        description = 'Use Open Shading Language (slower but can handle more complex layer setup)',
        default = False
    )

    use_dithering = BoolProperty(
        name = 'Use Dithering',
        description = 'Use dithering for less banding color',
        default = False
    )

    dither_intensity = FloatProperty(
        name = 'Dither Intensity',
        description = 'Amount of dithering noise added to the rendered image to break up banding',
        default=1.0, min=0.0, max=2.0, subtype='FACTOR'
    )

    bake_disabled_layers = BoolProperty(
        name = 'Bake Disabled Layers',  
        description = 'Take disabled layers into account when baking',
        default = False
    )

    # To store other objects info
    other_objects = CollectionProperty(type=YBakeInfoOtherObject)
    
    multires_base = IntProperty(default=1, min=0, max=16)

    hdr = BoolProperty(name='32 bit Float', default=False)

    # AO Props
    ao_distance = FloatProperty(default=1.0)

    # Bevel Props
    bevel_samples = IntProperty(default=4, min=2, max=16)
    bevel_radius = FloatProperty(default=0.05, min=0.0, max=1000.0)

    use_image_atlas = BoolProperty(
        name = 'Use Image Atlas',
        description = 'Use Image Atlas',
        default = False
    )

    vcol_force_first_ch_idx = StringProperty(
        name = 'Force First Vertex Color Channel',
        description = 'Force the first channel after baking the Vertex Color',
        default = 'Do Nothing'
    )

    selected_face_mode = BoolProperty(default=False)
    selected_objects = CollectionProperty(type=YBakeInfoSelectedObject)

    image_resolution = EnumProperty(
        name = 'Image Resolution',
        items = image_resolution_items,
        default = '1024'
    )
    
    use_custom_resolution = BoolProperty(
        name = 'Custom Resolution',
        default = False,
        description = 'Use custom Resolution to adjust the width and height individually'
    )

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

