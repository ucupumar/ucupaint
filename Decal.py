import bpy, re
from . import lib
from bpy.props import *
from bpy.app.handlers import persistent
from .common import *

def get_cylinder_projection_tree():
    tree_name = '~yPL Cylinder Projection'
    tree = bpy.data.node_groups.get(tree_name)
    if tree:
        return tree

    tree = bpy.data.node_groups.new(tree_name, 'ShaderNodeTree')
    # --- Setup Sockets ---
    if is_bl_newer_than(4, 0):
        tree.interface.new_socket('Vector', in_out='INPUT', socket_type='NodeSocketVector')
            
        s_dist = tree.interface.new_socket('Decal Distance', in_out='INPUT', socket_type='NodeSocketFloat')
        if hasattr(s_dist, 'default_value'):
            s_dist.default_value = 1.0

        s_scale = tree.interface.new_socket('Scale', in_out='INPUT', socket_type='NodeSocketVector')
        if hasattr(s_scale, 'default_value'):
            s_scale.default_value = (1.0, 1.0, 1.0)

        tree.interface.new_socket('Vector', in_out='OUTPUT', socket_type='NodeSocketVector')
        tree.interface.new_socket('Alpha Mask', in_out='OUTPUT', socket_type='NodeSocketFloat')
    else:
        new_tree_input(tree, 'Vector', 'NodeSocketVector')
        
        s_dist = new_tree_input(tree, 'Decal Distance', 'NodeSocketFloat')
        s_dist.default_value = 1.0

        s_scale = new_tree_input(tree, 'Scale', 'NodeSocketVector')
        s_scale.default_value = (1.0, 1.0, 1.0)

        new_tree_output(tree, 'Vector', 'NodeSocketVector')
        new_tree_output(tree, 'Alpha Mask', 'NodeSocketFloat')

    create_essential_nodes(tree)
    start = tree.nodes.get(TREE_START)
    end = tree.nodes.get(TREE_END)

    # --- 1. Gizmo Alignment: Rotate 90° on X ---
    vec_rot = tree.nodes.new('ShaderNodeVectorRotate')
    vec_rot.inputs['Axis'].default_value = (1.0, 0.0, 0.0)
    vec_rot.inputs['Angle'].default_value = math.radians(90)
    tree.links.new(start.outputs['Vector'], vec_rot.inputs['Vector'])

    # Separate unscaled rotated vector
    sep_rot = tree.nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(vec_rot.outputs['Vector'], sep_rot.inputs['Vector'])

    # Separate Scale input for horizontal (X) and vertical (Y) UV tiling
    sep_scale = tree.nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(start.outputs['Scale'], sep_scale.inputs['Vector'])

    # --- 2. Horizontal U (Azimuth Angle) + Scale Tiling ---
    # U_raw = atan2(Y, X) / (2 * pi) -> yields range [-0.5, 0.5]
    atan_u = tree.nodes.new('ShaderNodeMath')
    atan_u.operation = 'ARCTAN2'
    tree.links.new(sep_rot.outputs['Y'], atan_u.inputs[0])
    tree.links.new(sep_rot.outputs['X'], atan_u.inputs[1])

    norm_u = tree.nodes.new('ShaderNodeMath')
    norm_u.operation = 'MULTIPLY'
    norm_u.inputs[1].default_value = 1.0 / (2.0 * math.pi)
    tree.links.new(atan_u.outputs['Value'], norm_u.inputs[0])

    # Tile U using Scale.X
    scaled_u = tree.nodes.new('ShaderNodeMath')
    scaled_u.operation = 'MULTIPLY'
    tree.links.new(norm_u.outputs['Value'], scaled_u.inputs[0])
    tree.links.new(sep_scale.outputs['X'], scaled_u.inputs[1])

    # Center U at 0.5
    cyl_u = tree.nodes.new('ShaderNodeMath')
    cyl_u.operation = 'ADD'
    cyl_u.inputs[1].default_value = 0.5
    tree.links.new(scaled_u.outputs['Value'], cyl_u.inputs[0])

    # --- 3. Vertical V (Height Mapping) + Scale Tiling ---
    # V_raw = Z -> yields range [-0.5, 0.5]
    # Tile V using Scale.Y
    scaled_v = tree.nodes.new('ShaderNodeMath')
    scaled_v.operation = 'MULTIPLY'
    tree.links.new(sep_rot.outputs['Z'], scaled_v.inputs[0])
    tree.links.new(sep_scale.outputs['Y'], scaled_v.inputs[1])

    # Center V at 0.5
    cyl_v = tree.nodes.new('ShaderNodeMath')
    cyl_v.operation = 'ADD'
    cyl_v.inputs[1].default_value = 0.5
    tree.links.new(scaled_v.outputs['Value'], cyl_v.inputs[0])

    # Combine into UV output vector
    cyl_uv = tree.nodes.new('ShaderNodeCombineXYZ')
    tree.links.new(cyl_u.outputs['Value'], cyl_uv.inputs['X'])
    tree.links.new(cyl_v.outputs['Value'], cyl_uv.inputs['Y'])

    # --- 4. Cylindrical Boundary Mask (Based on Gizmo Size) ---
    # Radial XY Distance: length(X, Y)
    xy_comb = tree.nodes.new('ShaderNodeCombineXYZ')
    tree.links.new(sep_rot.outputs['X'], xy_comb.inputs['X'])
    tree.links.new(sep_rot.outputs['Y'], xy_comb.inputs['Y'])

    xy_len = tree.nodes.new('ShaderNodeVectorMath')
    xy_len.operation = 'LENGTH'
    tree.links.new(xy_comb.outputs['Vector'], xy_len.inputs[0])

    # Z Depth Distance: |Z|
    abs_z = tree.nodes.new('ShaderNodeMath')
    abs_z.operation = 'ABSOLUTE'
    tree.links.new(sep_rot.outputs['Z'], abs_z.inputs[0])

    half_dist = tree.nodes.new('ShaderNodeMath')
    half_dist.operation = 'MULTIPLY'
    half_dist.inputs[1].default_value = 0.5
    tree.links.new(start.outputs['Decal Distance'], half_dist.inputs[0])

    # Combine Masks
    mask_xy = tree.nodes.new('ShaderNodeMath')
    mask_xy.operation = 'LESS_THAN'
    tree.links.new(xy_len.outputs['Value'], mask_xy.inputs[0])
    tree.links.new(half_dist.outputs['Value'], mask_xy.inputs[1])

    mask_z = tree.nodes.new('ShaderNodeMath')
    mask_z.operation = 'LESS_THAN'
    tree.links.new(abs_z.outputs['Value'], mask_z.inputs[0])
    tree.links.new(half_dist.outputs['Value'], mask_z.inputs[1])

    mask_cyl = tree.nodes.new('ShaderNodeMath')
    mask_cyl.operation = 'MULTIPLY'
    tree.links.new(mask_xy.outputs['Value'], mask_cyl.inputs[0])
    tree.links.new(mask_z.outputs['Value'], mask_cyl.inputs[1])

    # --- Outputs ---
    tree.links.new(cyl_uv.outputs['Vector'], end.inputs['Vector'])
    tree.links.new(mask_cyl.outputs['Value'], end.inputs['Alpha Mask'])

    return tree

def get_sphere_projection_tree():
    tree_name = '~yPL Sphere Projection'
    tree = bpy.data.node_groups.get(tree_name)
    if tree:
        return tree

    tree = bpy.data.node_groups.new(tree_name, 'ShaderNodeTree')
    # --- Setup Sockets ---
    if is_bl_newer_than(4, 0):
        tree.interface.new_socket('Vector', in_out='INPUT', socket_type='NodeSocketVector')
            
        s_dist = tree.interface.new_socket('Decal Distance', in_out='INPUT', socket_type='NodeSocketFloat')
        if hasattr(s_dist, 'default_value'):
            s_dist.default_value = 1.0

        s_scale = tree.interface.new_socket('Scale', in_out='INPUT', socket_type='NodeSocketVector')
        if hasattr(s_scale, 'default_value'):
            s_scale.default_value = (1.0, 1.0, 1.0)

        tree.interface.new_socket('Vector', in_out='OUTPUT', socket_type='NodeSocketVector')
        tree.interface.new_socket('Alpha Mask', in_out='OUTPUT', socket_type='NodeSocketFloat')
    else:
        new_tree_input(tree, 'Vector', 'NodeSocketVector')
        
        s_dist = new_tree_input(tree, 'Decal Distance', 'NodeSocketFloat')
        s_dist.default_value = 1.0

        s_scale = new_tree_input(tree, 'Scale', 'NodeSocketVector')
        s_scale.default_value = (1.0, 1.0, 1.0)

        new_tree_output(tree, 'Vector', 'NodeSocketVector')
        new_tree_output(tree, 'Alpha Mask', 'NodeSocketFloat')

    create_essential_nodes(tree)
    start = tree.nodes.get(TREE_START)
    end = tree.nodes.get(TREE_END)

    # --- 1. Cast from Center Outwards (Normalize Unscaled Vector) ---
    vec_norm = tree.nodes.new('ShaderNodeVectorMath')
    vec_norm.operation = 'NORMALIZE'
    tree.links.new(start.outputs['Vector'], vec_norm.inputs[0])

    sep_norm = tree.nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(vec_norm.outputs['Vector'], sep_norm.inputs['Vector'])

    # Separate Scale input for horizontal (X) and vertical (Y) UV tiling
    sep_scale = tree.nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(start.outputs['Scale'], sep_scale.inputs['Vector'])

    # --- 2. Horizontal U (Angle around central Z-axis) + Scale Tiling ---
    # U_raw = atan2(Y_norm, X_norm) / (2 * pi) -> yields range [-0.5, 0.5]
    atan_u = tree.nodes.new('ShaderNodeMath')
    atan_u.operation = 'ARCTAN2'
    tree.links.new(sep_norm.outputs['Y'], atan_u.inputs[0])
    tree.links.new(sep_norm.outputs['X'], atan_u.inputs[1])

    norm_u = tree.nodes.new('ShaderNodeMath')
    norm_u.operation = 'MULTIPLY'
    norm_u.inputs[1].default_value = 1.0 / (2.0 * math.pi)
    tree.links.new(atan_u.outputs['Value'], norm_u.inputs[0])

    # Tile U using Scale.X
    scaled_u = tree.nodes.new('ShaderNodeMath')
    scaled_u.operation = 'MULTIPLY'
    tree.links.new(norm_u.outputs['Value'], scaled_u.inputs[0])
    tree.links.new(sep_scale.outputs['X'], scaled_u.inputs[1])

    # Center U at 0.5
    sphere_u = tree.nodes.new('ShaderNodeMath')
    sphere_u.operation = 'ADD'
    sphere_u.inputs[1].default_value = 0.5
    tree.links.new(scaled_u.outputs['Value'], sphere_u.inputs[0])

    # --- 3. Vertical V (Latitude / Z height) + Scale Tiling ---
    # V_raw = Z_norm * 0.5 -> yields range [-0.5, 0.5]
    mult_v = tree.nodes.new('ShaderNodeMath')
    mult_v.operation = 'MULTIPLY'
    mult_v.inputs[1].default_value = 0.5
    tree.links.new(sep_norm.outputs['Z'], mult_v.inputs[0])

    # Tile V using Scale.Y
    scaled_v = tree.nodes.new('ShaderNodeMath')
    scaled_v.operation = 'MULTIPLY'
    tree.links.new(mult_v.outputs['Value'], scaled_v.inputs[0])
    tree.links.new(sep_scale.outputs['Y'], scaled_v.inputs[1])

    # Center V at 0.5
    sphere_v = tree.nodes.new('ShaderNodeMath')
    sphere_v.operation = 'ADD'
    sphere_v.inputs[1].default_value = 0.5
    tree.links.new(scaled_v.outputs['Value'], sphere_v.inputs[0])

    # Combine into UV output vector
    sphere_uv = tree.nodes.new('ShaderNodeCombineXYZ')
    tree.links.new(sphere_u.outputs['Value'], sphere_uv.inputs['X'])
    tree.links.new(sphere_v.outputs['Value'], sphere_uv.inputs['Y'])

    # --- 4. Radial Distance Mask (3D distance from center < Decal Distance * 0.5) ---
    vec_len = tree.nodes.new('ShaderNodeVectorMath')
    vec_len.operation = 'LENGTH'
    tree.links.new(start.outputs['Vector'], vec_len.inputs[0])

    half_dist = tree.nodes.new('ShaderNodeMath')
    half_dist.operation = 'MULTIPLY'
    half_dist.inputs[1].default_value = 0.5
    tree.links.new(start.outputs['Decal Distance'], half_dist.inputs[0])

    mask_r = tree.nodes.new('ShaderNodeMath')
    mask_r.operation = 'LESS_THAN'
    tree.links.new(vec_len.outputs['Value'], mask_r.inputs[0])
    tree.links.new(half_dist.outputs['Value'], mask_r.inputs[1])

    # --- Outputs ---
    tree.links.new(sphere_uv.outputs['Vector'], end.inputs['Vector'])
    tree.links.new(mask_r.outputs['Value'], end.inputs['Alpha Mask'])

    return tree

def get_plane_projection_tree():
    """Pure planar projection: Infinite XY plane projection with Z-axis distance clipping."""
    tree_name = '~yPL Plane Projection'
    tree = bpy.data.node_groups.get(tree_name)
    if tree:
        return tree

    tree = bpy.data.node_groups.new(tree_name, 'ShaderNodeTree')
    # --- Setup Sockets ---
    if is_bl_newer_than(4, 0):
        tree.interface.new_socket('Vector', in_out='INPUT', socket_type='NodeSocketVector')
            
        s_dist = tree.interface.new_socket('Decal Distance', in_out='INPUT', socket_type='NodeSocketFloat')
        if hasattr(s_dist, 'default_value'):
            s_dist.default_value = 1.0

        s_scale = tree.interface.new_socket('Scale', in_out='INPUT', socket_type='NodeSocketVector')
        if hasattr(s_scale, 'default_value'):
            s_scale.default_value = (1.0, 1.0, 1.0)

        tree.interface.new_socket('Vector', in_out='OUTPUT', socket_type='NodeSocketVector')
        tree.interface.new_socket('Alpha Mask', in_out='OUTPUT', socket_type='NodeSocketFloat')
    else:
        new_tree_input(tree, 'Vector', 'NodeSocketVector')
        
        s_dist = new_tree_input(tree, 'Decal Distance', 'NodeSocketFloat')
        s_dist.default_value = 1.0

        s_scale = new_tree_input(tree, 'Scale', 'NodeSocketVector')
        s_scale.default_value = (1.0, 1.0, 1.0)

        new_tree_output(tree, 'Vector', 'NodeSocketVector')
        new_tree_output(tree, 'Alpha Mask', 'NodeSocketFloat')

    create_essential_nodes(tree)
    start = tree.nodes.get(TREE_START)
    end = tree.nodes.get(TREE_END)

    # --- 1. UV Projection (Scaled XY + 0.5 offset) ---
    vec_div = tree.nodes.new('ShaderNodeVectorMath')
    vec_div.operation = 'DIVIDE'
    tree.links.new(start.outputs['Vector'], vec_div.inputs[0])
    tree.links.new(start.outputs['Scale'], vec_div.inputs[1])

    sep_scaled = tree.nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(vec_div.outputs['Vector'], sep_scaled.inputs['Vector'])

    flat_u = tree.nodes.new('ShaderNodeMath')
    flat_u.operation = 'ADD'
    flat_u.inputs[1].default_value = 0.5
    tree.links.new(sep_scaled.outputs['X'], flat_u.inputs[0])

    flat_v = tree.nodes.new('ShaderNodeMath')
    flat_v.operation = 'ADD'
    flat_v.inputs[1].default_value = 0.5
    tree.links.new(sep_scaled.outputs['Y'], flat_v.inputs[0])

    flat_uv = tree.nodes.new('ShaderNodeCombineXYZ')
    tree.links.new(flat_u.outputs['Value'], flat_uv.inputs['X'])
    tree.links.new(flat_v.outputs['Value'], flat_uv.inputs['Y'])

    # --- 2. Z Distance Depth Mask (|Z| < Decal Distance * 0.5) ---
    sep_raw = tree.nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(start.outputs['Vector'], sep_raw.inputs['Vector'])

    abs_z = tree.nodes.new('ShaderNodeMath')
    abs_z.operation = 'ABSOLUTE'
    tree.links.new(sep_raw.outputs['Z'], abs_z.inputs[0])

    half_dist = tree.nodes.new('ShaderNodeMath')
    half_dist.operation = 'MULTIPLY'
    half_dist.inputs[1].default_value = 0.5
    tree.links.new(start.outputs['Decal Distance'], half_dist.inputs[0])

    mask_z = tree.nodes.new('ShaderNodeMath')
    mask_z.operation = 'LESS_THAN'
    tree.links.new(abs_z.outputs['Value'], mask_z.inputs[0])
    tree.links.new(half_dist.outputs['Value'], mask_z.inputs[1])

    # --- Outputs ---
    tree.links.new(flat_uv.outputs['Vector'], end.inputs['Vector'])
    tree.links.new(mask_z.outputs['Value'], end.inputs['Alpha Mask'])

    return tree

def get_decal_process_tree():
    """Main '~yPL Decal Process' ShaderNodeTree wrapping projection sub-trees."""
    tree_name = lib.DECAL_PROCESS
    tree = bpy.data.node_groups.get(tree_name)
    if tree:
        return tree

    tree = bpy.data.node_groups.new(tree_name, 'ShaderNodeTree')

    # --- Setup Interface Sockets ---
    if is_bl_newer_than(4, 0):
        tree.interface.new_socket('Vector', in_out='INPUT', socket_type='NodeSocketVector')
            
        inp_dist = tree.interface.new_socket('Decal Distance', in_out='INPUT', socket_type='NodeSocketFloat')
        if hasattr(inp_dist, 'default_value'):
            inp_dist.default_value = 1.0

        inp_scale = tree.interface.new_socket('Scale', in_out='INPUT', socket_type='NodeSocketVector')
        if hasattr(inp_scale, 'default_value'):
            inp_scale.default_value = (1.0, 1.0, 1.0)   


        tree.interface.new_socket('Vector', in_out='OUTPUT', socket_type='NodeSocketVector')
        tree.interface.new_socket('Alpha Mask', in_out='OUTPUT', socket_type='NodeSocketFloat')
    else:
        new_tree_input(tree, 'Vector', 'NodeSocketVector')

        
        inp_dist = new_tree_input(tree, 'Decal Distance', 'NodeSocketFloat')
        inp_dist.default_value = 1.0

        inp_scale = new_tree_input(tree, 'Scale', 'NodeSocketVector')
        inp_scale.default_value = (1.0, 1.0, 1.0)

        new_tree_output(tree, 'Vector', 'NodeSocketVector')
        new_tree_output(tree, 'Alpha Mask', 'NodeSocketFloat')

    create_essential_nodes(tree)
    start = tree.nodes.get(TREE_START)
    end = tree.nodes.get(TREE_END)

    # --- Add Plane Projection Sub-Group ---
    plane_node = tree.nodes.new('ShaderNodeGroup')
    plane_node.node_tree = get_plane_projection_tree()

    # Pass main inputs to sub-group
    tree.links.new(start.outputs['Vector'], plane_node.inputs['Vector'])
    tree.links.new(start.outputs['Scale'], plane_node.inputs['Scale'])
    tree.links.new(start.outputs['Decal Distance'], plane_node.inputs['Decal Distance'])

    # Pass sub-group outputs to main outputs
    tree.links.new(plane_node.outputs['Vector'], end.inputs['Vector'])
    tree.links.new(plane_node.outputs['Alpha Mask'], end.inputs['Alpha Mask'])

    return tree

def get_decal_object(entity):
    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: tree = get_tree(entity)
    elif m2: tree = get_mask_tree(entity)
    else: return None

    decal_obj = None
    texcoord = tree.nodes.get(entity.texcoord)
    if texcoord and hasattr(texcoord, 'object'): decal_obj = texcoord.object

    return decal_obj

def get_decal_shrinkwrap_constraint(decal_obj):
    cs = [c for c in decal_obj.constraints if c.type == 'SHRINKWRAP']
    if len(cs) > 0: return cs[0]
    return None

def any_decal_inside_layer(layer):
    if layer.texcoord_type == 'Decal':
        return True

    for mask in layer.masks:
        if mask.texcoord_type == 'Decal':
            return True

    return False

def remove_decal_object(tree, entity):
    if not tree: return
    # NOTE: This will remove the texcoord object even if the entity is not using decal
    #if entity.texcoord_type == 'Decal':
    texcoord = tree.nodes.get(entity.texcoord)
    if texcoord and hasattr(texcoord, 'object') and texcoord.object:
        decal_obj = texcoord.object
        if decal_obj.type == 'EMPTY' and decal_obj.users <= 2:
            texcoord.object = None
            remove_datablock(bpy.data.objects, decal_obj)

decal_projection_items = (
    ('FLAT', "Flat", "Flat projection"),
    ('CYLINDER', "Cylinder", "Cylindrical projection"),
    ('SPHERE', "Sphere", "Spherical projection"),
)

def set_projection_gizmo(proj_node, mode):
    if not proj_node:
        return

    match mode:
        case 'SPHERE':
            new_tree = get_sphere_projection_tree()
        case 'CYLINDER':
            new_tree = get_cylinder_projection_tree()
        case _:
            new_tree = get_plane_projection_tree()

    # Swap tree if changed
    old_tree = proj_node.node_tree
    if old_tree != new_tree:
        proj_node.node_tree = new_tree

        # Clean up
        if old_tree and old_tree.users == 0:
            bpy.data.node_groups.remove(old_tree)

def set_projection_mode(proj_node, mode):
    if not proj_node:
        return

    match mode:
        case 'SPHERE':
            new_tree = get_sphere_projection_tree()
        case 'CYLINDER':
            new_tree = get_cylinder_projection_tree()
        case _:
            new_tree = get_plane_projection_tree()

    # Swap tree if changed
    old_tree = proj_node.node_tree
    if old_tree != new_tree:
        proj_node.node_tree = new_tree

        # Clean up
        if old_tree and old_tree.users == 0:
            bpy.data.node_groups.remove(old_tree)


def update_decal_projection(self, context):
    entity = self
    
    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: 
        tree = get_tree(entity)
    elif m2: 
        tree = get_mask_tree(entity)

      
    if not tree:
        return
    
    decal_node = tree.nodes.get(getattr(entity, 'decal_process', ''))
    if not decal_node or not decal_node.node_tree:
        return

    #Split decal nodes
    if decal_node.node_tree.users > 1:
        decal_node.node_tree = decal_node.node_tree.copy()

    proj_node = None
    for node in decal_node.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree:
            if re.match(r'^~yPL .+ Projection$', node.node_tree.name):
                proj_node = node
                break

    if not proj_node:
        return
    
    mode = getattr(entity, 'decal_projection_type', 'FLAT')

    set_projection_mode(proj_node, mode)

def update_enable_uniform_scale(self, context):
    """Fired when toggling the lock icon."""
    if self.enable_uniform:
        # Lock Y and Z to X's current scale value
        val = self.decal_scale[0]
        self.uniform_scale = val
        self.decal_scale = (val, val, val)
    

def update_decal_scale(self, context):
    """Fired when editing decal_scale vector components."""
    if getattr(self, 'enable_uniform', False):
        # Prevent recursion by checking if values actually differ
        val = self.decal_scale[0]
        # Keep all axes locked together
        if self.decal_scale[1] != val or self.decal_scale[2] != val:
            self.decal_scale = (val, val, val)
            self.uniform_scale = val


def update_uniform_scale(self, context):
    """Fired when uniform_scale changes."""
    if getattr(self, 'enable_uniform', False):
        val = self.uniform_scale
        self.decal_scale = (val, val, val)

def update_enable_decal_object_constraint(self, context):
    obj = context.object
    decal_obj = self.id_data
    decal_const = get_decal_shrinkwrap_constraint(decal_obj)

    if self.enable_shrinkwrap:
        if not decal_const and obj:
            c = decal_obj.constraints.new('SHRINKWRAP')
            c.target = obj
            if is_bl_newer_than(2, 80):
                c.use_track_normal = True
                c.track_axis = 'TRACK_Z'
    else:
        if decal_const:
            decal_obj.constraints.remove(decal_const)

def create_decal_empty():
    obj = bpy.context.object
    scene = bpy.context.scene
    empty_name = get_unique_name('Decal', bpy.data.objects)
    empty = bpy.data.objects.new(empty_name, None)



    if is_bl_newer_than(2, 80):
        empty.empty_display_type = 'SINGLE_ARROW'
    else: 
        empty.empty_draw_type = 'SINGLE_ARROW'


    custom_collection = obj.users_collection[0] if is_bl_newer_than(2, 80) and len(obj.users_collection) > 0 else None
    link_object(scene, empty, custom_collection)

    if is_bl_newer_than(2, 80):
        empty.location = scene.cursor.location.copy()
        empty.rotation_euler = scene.cursor.rotation_euler.copy()
    else: 
        empty.location = scene.cursor_location.copy()

    empty.parent = obj
    empty.matrix_parent_inverse = obj.matrix_world.inverted()

    return empty

def check_entity_decal_nodes(entity, tree=None):
    yp = entity.id_data.yp
    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: 
        entity_enabled = get_layer_enabled(entity)
        source = get_layer_source(entity)
        if not tree: tree = get_tree(entity)
        layer = entity
        mask = None
    elif m2: 
        entity_enabled = get_mask_enabled(entity)
        source = get_mask_source(entity)
        layer = yp.layers[int(m2.group(1))]
        if not tree: tree = get_tree(entity)
        mask = entity
    else: 
        return

    # Get height channel
    height_ch = get_height_channel(layer)

    texcoord = tree.nodes.get(entity.texcoord)
    if entity_enabled and entity.texcoord_type == 'Decal' and is_mapping_possible(entity.type):

        # 1. Fetch image source early
        image = None
        if entity.type == 'IMAGE' and source:
            image = source.image

        # 2. Projection type setup
        proj_type = getattr(entity, 'decal_projection_type', 'FLAT')

        # 3. Create or update TexCoord empty object
        if not texcoord:
            empty = create_decal_empty()
            texcoord = new_node(tree, entity, 'texcoord', 'ShaderNodeTexCoord', 'TexCoord')
            texcoord.object = empty
        elif hasattr(texcoord, 'object') and texcoord.object:
            display_map = {'FLAT': 'SINGLE_ARROW', 'CYLINDER': 'CIRCLE', 'SPHERE': 'SPHERE'}
            texcoord.object.empty_display_type = 'SINGLE_ARROW'

        # 4. Create or fetch Decal Process group node
        decal_process = tree.nodes.get(entity.decal_process)
        if not decal_process:
            decal_process = new_node(tree, entity, 'decal_process', 'ShaderNodeGroup', 'Decal Process')
            decal_process.node_tree = get_decal_process_tree()

            if image and source:
                entity.original_image_extension = source.extension
                source.extension = 'CLIP'

        # 5. Connect TexCoord Object vector output -> Decal Process input
        if 'Object' in texcoord.outputs and 'Vector' in decal_process.inputs:
            tree.links.new(texcoord.outputs['Object'], decal_process.inputs['Vector'])

        # 6. Pass Decal Distance value
        if 'Decal Distance' in decal_process.inputs:
            decal_process.inputs['Decal Distance'].default_value = getattr(entity, 'decal_distance_value', 1.0)

        scale_x, scale_y, scale_z = 1.0, 1.0, 1.0

        # 1. Base scale from image aspect ratio
        if image and image.size[0] > 0 and image.size[1] > 0:
            if image.size[0] > image.size[1]:
                scale_x = image.size[1] / image.size[0]
            else:
                scale_y = image.size[0] / image.size[1]

        # 2. Combine with material layer scale property
        layer_scale = getattr(entity, 'scale', None) or getattr(entity, 'mapping_scale', None)
        if layer_scale:
            scale_x *= layer_scale[0]
            scale_y *= layer_scale[1]
            scale_z *= layer_scale[2]

        if 'Scale' in decal_process.inputs:
            decal_process.inputs['Scale'].default_value = (scale_x, scale_y, scale_z)

        # 7. Pass Projection Type integer (if node group supports multi-projection)
        if 'Projection Type' in decal_process.inputs:
            proj_map = {'FLAT': 0, 'CYLINDER': 1, 'SPHERE': 2}
            decal_process.inputs['Projection Type'].default_value = proj_map.get(proj_type, 0)

        # 8. Set decal aspect ratio scale
        scale_x, scale_y, scale_z = 1.0, 1.0, 1.0

        if image and image.size[0] > 0 and image.size[1] > 0:
            if image.size[0] > image.size[1]:
                scale_x = image.size[1] / image.size[0]
            else:
                scale_y = image.size[0] / image.size[1]

        if getattr(entity, 'enable_uniform_scale', False):
            u_scale = getattr(entity, 'uniform_scale_value', 1.0)
            scale_x *= u_scale
            scale_y *= u_scale
            scale_z *= u_scale
        else:
            user_scale = (
                getattr(entity, 'decal_scale', None) or 
                getattr(entity, 'scale', None) or (1.0, 1.0, 1.0)
            )
            scale_x *= user_scale[0]
            scale_y *= user_scale[1]
            scale_z *= user_scale[2]

        scale_input = decal_process.inputs.get('Scale')
        if scale_input:
            scale_input.default_value = (scale_x, scale_y, scale_z)

        # 9. Create decal alpha math nodes
        if mask:
            height_root_ch = get_root_height_channel(yp)
            height_ch_enabled = get_channel_enabled(height_ch) if height_ch else False

            decal_alpha = check_new_node(tree, mask, 'decal_alpha', 'ShaderNodeMath', 'Decal Alpha')
            if decal_alpha.operation != 'MULTIPLY':
                decal_alpha.operation = 'MULTIPLY'

            if height_ch and height_ch_enabled and height_root_ch.enable_smooth_bump:
                for letter in nsew_letters:
                    decal_alpha = check_new_node(tree, mask, 'decal_alpha_' + letter, 'ShaderNodeMath', 'Decal Alpha ' + letter.upper())
                    if decal_alpha.operation != 'MULTIPLY':
                        decal_alpha.operation = 'MULTIPLY'
            else:
                for letter in nsew_letters:
                    remove_node(tree, mask, 'decal_alpha_' + letter)

        else:
            for i, ch in enumerate(layer.channels):
                root_ch = yp.channels[i]
                ch_enabled = get_channel_enabled(ch)
                if ch_enabled:
                    decal_alpha = check_new_node(tree, ch, 'decal_alpha', 'ShaderNodeMath', 'Decal Alpha')
                    if decal_alpha.operation != 'MULTIPLY':
                        decal_alpha.operation = 'MULTIPLY'
                else:
                    remove_node(tree, ch, 'decal_alpha')

                if root_ch.type == 'NORMAL':
                    if ch_enabled and root_ch.enable_smooth_bump:
                        for letter in nsew_letters:
                            decal_alpha = check_new_node(tree, ch, 'decal_alpha_' + letter, 'ShaderNodeMath', 'Decal Alpha ' + letter.upper())
                            if decal_alpha.operation != 'MULTIPLY':
                                decal_alpha.operation = 'MULTIPLY'
                    else:
                        for letter in nsew_letters:
                            remove_node(tree, ch, 'decal_alpha_' + letter)

    else:
        # Cleanup when decal mode is disabled or mapped away
        if not texcoord or not hasattr(texcoord, 'object') or not texcoord.object: 
            remove_node(tree, entity, 'texcoord')
        remove_node(tree, entity, 'decal_process')

        if mask: 
            remove_node(tree, mask, 'decal_alpha')
            if height_ch:
                for letter in nsew_letters:
                    remove_node(tree, mask, 'decal_alpha_' + letter)
        else:
            for i, ch in enumerate(layer.channels):
                root_ch = yp.channels[i]
                remove_node(tree, ch, 'decal_alpha')

                if root_ch.type == 'NORMAL':
                    for letter in nsew_letters:
                        remove_node(tree, ch, 'decal_alpha_' + letter)

        # Recover image extension type
        if entity.type == 'IMAGE' and entity.original_texcoord == 'Decal' and entity.original_image_extension != '':
            source = get_mask_source(mask) if mask else get_layer_source(layer)
            if source:
                source.extension = entity.original_image_extension
                entity.original_image_extension = ''

    # Save original texcoord type
    if entity.original_texcoord != entity.texcoord_type:
        entity.original_texcoord = entity.texcoord_type

class YSelectDecalObject(bpy.types.Operator):
    bl_idname = "wm.y_select_decal_object"
    bl_label = "Select Decal Object"
    bl_description = "Select Decal Object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return group_node and hasattr(context, 'entity')

    def execute(self, context):
        scene = context.scene

        decal_obj = get_decal_object(context.entity)
        if decal_obj:
            try: bpy.ops.object.mode_set(mode='OBJECT')
            except: pass
            bpy.ops.object.select_all(action='DESELECT')
            if decal_obj.name not in get_scene_objects():
                parent = decal_obj.parent
                custom_collection = parent.users_collection[0] if is_bl_newer_than(2, 80) and parent and len(parent.users_collection) > 0 else None
                link_object(scene, decal_obj, custom_collection)
            set_active_object(decal_obj)
            set_object_select(decal_obj, True)
        else: return {'CANCELLED'}

        return {'FINISHED'}

class YSetDecalObjectPositionToCursor(bpy.types.Operator):
    bl_idname = "wm.y_set_decal_object_position_to_sursor"
    bl_label = "Set Decal Position to Cursor"
    bl_description = "Set the position of the decal object to the 3D cursor"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return group_node and hasattr(context, 'entity')

    def execute(self, context):
        scene = bpy.context.scene
        entity = context.entity

        m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
        m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

        if m1: tree = get_tree(entity)
        elif m2: tree = get_mask_tree(entity)
        else: return {'CANCELLED'}

        texcoord = tree.nodes.get(entity.texcoord)

        if texcoord and hasattr(texcoord, 'object') and texcoord.object:
            # Move decal object to 3D cursor
            if is_bl_newer_than(2, 80):
                texcoord.object.location = scene.cursor.location.copy()
                texcoord.object.rotation_euler = scene.cursor.rotation_euler.copy()
            else: 
                texcoord.object.location = scene.cursor_location.copy()

        else: return {'CANCELLED'}

        return {'FINISHED'}

class BaseDecal():
    enable_uniform: BoolProperty(
        name='Uniform Scale',
        default=False,
        update=update_enable_uniform_scale
    )

    uniform_scale: FloatProperty(
        name='Uniform Scale Value',
        default=1.0,
        update=update_uniform_scale
    )

    decal_scale: FloatVectorProperty(
        name='Scale',
        default=(1.0, 1.0, 1.0),
        size=3,
        subtype='XYZ',
        update=update_decal_scale
    )

    decal_projection_type: EnumProperty(
        name='Projection',
        description='Decal projection mapping mode',
        items=decal_projection_items,
        default='FLAT',
        update=update_decal_projection
    )

    decal_distance_value : FloatProperty(
        name = 'Decal Distance',
        description = 'Distance between surface and the decal object',
        min=0.0, max=100.0, default=0.5, precision=3
    )

    original_texcoord : EnumProperty(
        name = 'Original Texture Coordinate Type',
        items = mask_texcoord_type_items,
        default = 'UV'
    )

    original_image_extension : StringProperty(
        name = 'Original Image Extension Type',
        default = ''
    )


class YPaintDecalObjectProps(bpy.types.PropertyGroup):
    enable_shrinkwrap : BoolProperty(
        name = 'Enable Decal Shrinkwrap Constraint',
        description = 'Enable shrinkwrap constraint, so decal object always follow the target object',
        default = False,
        update = update_enable_decal_object_constraint
    )

    last_operator : StringProperty(default='')
    last_operator_pointer : StringProperty(default='')

def apply_decal_constraint_transforms(op):
    for obj in bpy.context.selected_objects:
        if not obj.yp_decal.enable_shrinkwrap: continue

        # Get constraint
        c = get_decal_shrinkwrap_constraint(obj)
        if not c or c.mute: continue

        if obj.yp_decal.last_operator != op.bl_idname or obj.yp_decal.last_operator_pointer != str(op.as_pointer()):
            obj.yp_decal.last_operator = op.bl_idname
            obj.yp_decal.last_operator_pointer = str(op.as_pointer())

            # Apply the constraint after transforming
            mat = obj.matrix_world.copy()
            try: 
                c.mute = True
                obj.matrix_world = mat
                c.mute = False
            except Exception as e: print('EXCEPTIION:', e)

@persistent
def ypaint_decal_constraint_update(scene):
    # NOTE: Only apply constraint transformations when the active object enable the decal contstraint flag
    # This is to improve performance since there's no need to check every selected objects
    obj = bpy.context.object if hasattr(bpy.context, 'object') else None
    if obj and obj.yp_decal.enable_shrinkwrap and bpy.context.active_operator:
        op = bpy.context.active_operator
        # NOTE: Using depsgraph updates is slightly faster than using `startswith`, but only works on Blender 2.80+
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for update in depsgraph.updates:
            if update.is_updated_transform:
                apply_decal_constraint_transforms(op)
                break

@persistent
def ypaint_decal_constraint_update_legacy(scene):
    # NOTE: Only apply constraint transformations when the active object enable the decal contstraint flag
    # This is to improve performance since there's no need to check every selected objects
    obj = bpy.context.object
    if obj and obj.yp_decal.enable_shrinkwrap and bpy.context.active_operator:
        op = bpy.context.active_operator
        if op.bl_idname.startswith('TRANSFORM_OT'):
            apply_decal_constraint_transforms(op)

def register():
    bpy.utils.register_class(YSelectDecalObject)
    bpy.utils.register_class(YSetDecalObjectPositionToCursor)
    bpy.utils.register_class(YPaintDecalObjectProps)

    # YPaint Props
    bpy.types.Object.yp_decal = PointerProperty(type=YPaintDecalObjectProps)

    # Handlers
    if is_bl_newer_than(2, 80):
        bpy.app.handlers.depsgraph_update_post.append(ypaint_decal_constraint_update)
    else: bpy.app.handlers.scene_update_pre.append(ypaint_decal_constraint_update_legacy)

def unregister():
    bpy.utils.unregister_class(YSelectDecalObject)
    bpy.utils.unregister_class(YSetDecalObjectPositionToCursor)
    bpy.utils.unregister_class(YPaintDecalObjectProps)

    # Handlers
    if is_bl_newer_than(2, 80):
        bpy.app.handlers.depsgraph_update_post.remove(ypaint_decal_constraint_update)
    else: bpy.app.handlers.scene_update_pre.remove(ypaint_decal_constraint_update_legacy)
