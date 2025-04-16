from mathutils import *
from .common import *

NO_MODIFIER_Y_OFFSET = 200
FINE_BUMP_Y_OFFSET = 300

default_y_offsets = {
    'RGB' : 165,
    'VALUE' : 220,
    'NORMAL' : 155,
}

mod_y_offsets = {
    'INVERT' : 330,
    'RGB_TO_INTENSITY' : 280,
    'INTENSITY_TO_RGB' : 280,
    'OVERRIDE_COLOR' : 280,
    'COLOR_RAMP' : 315,
    'RGB_CURVE' : 390,
    'HUE_SATURATION' : 265,
    'BRIGHT_CONTRAST' : 220,
    'MULTIPLIER' :  350,
    'MATH' : 350
}

value_mod_y_offsets = {
    'INVERT' : 270,
    'MULTIPLIER' :  270,
    'MATH' : 270
}

def get_mod_y_offsets(mod, is_value=False):
    if is_value and mod.type in value_mod_y_offsets:
        return value_mod_y_offsets[mod.type]
    return mod_y_offsets[mod.type]

def check_set_node_loc(tree, node_name, loc, hide=False, parent_unset=False):
    node = tree.nodes.get(node_name)
    if node:
        # Blender 4.4+ has new parent and node calculation
        if is_bl_newer_than(4, 4) and node.parent != None:
            if node.location != loc - node.parent.location:
                node.location = loc - node.parent.location

        elif node.location != loc:
            node.location = loc

        if node.hide != hide:
            node.hide = hide

        if parent_unset and node.parent != None:
            node.parent = None

        return True
    return False

def check_set_node_loc_x(tree, node_name, loc_x): #, hide=False):
    node = tree.nodes.get(node_name)
    if node:
        if node.location.x != loc_x:
            node.location.x = loc_x
        #if node.hide != hide:
        #    node.hide = hide
        return True
    return False

def check_set_node_loc_y(tree, node_name, loc_y): #, hide=False):
    node = tree.nodes.get(node_name)
    if node:
        if node.location.y != loc_y:
            node.location.y = loc_y
        #if node.hide != hide:
        #    node.hide = hide
        return True
    return False

def check_set_node_width(node, width):
    if node:
        if node.width != width:
            node.width = width
        return True
    return False

def check_set_node_parent(tree, child_name, parent_node):
    child = tree.nodes.get(child_name)
    if child and child.parent != parent_node:
        child.parent = parent_node

def set_node_label(node, label):
    if node and node.label != label:
        node.label = label

def get_frame(tree, name, suffix='', label=''):

    frame_name = name + suffix

    frame = tree.nodes.get(frame_name)
    if not frame:
        frame = tree.nodes.new('NodeFrame')
        frame.name = frame_name

    if frame.label != label:
        frame.label = label

    return frame

def clean_unused_frames(tree):

    #T = time.time()

    # Collect all parents and frames
    parents = []
    frames = []
    for node in tree.nodes:
        if node.parent and node.parent not in parents:
            parents.append(node.parent)
        if node.type == 'FRAME' and not node.name.startswith(INFO_PREFIX):
            frames.append(node)

    # Remove frame with no child
    for frame in frames:
        if frame not in parents:
            tree.nodes.remove(frame)

    #print('INFO: Unused frames cleaned in ', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def rearrange_yp_frame_nodes(yp):
    tree = yp.id_data
    nodes = tree.nodes

    # Channel loops
    for i, ch in enumerate(yp.channels):

        ## Start Frame
        #frame = get_frame(tree, '__start__', str(i), ch.name + ' Start')
        #check_set_node_parent(tree, ch.start_linear, frame)
        #check_set_node_parent(tree, ch.start_normal_filter, frame)

        # End Frame
        #frame = get_frame(tree, '__end__', str(i), ch.name + ' End')
        #check_set_node_parent(tree, ch.start_rgb, frame)
        #check_set_node_parent(tree, ch.start_alpha, frame)
        #check_set_node_parent(tree, ch.end_rgb, frame)
        #check_set_node_parent(tree, ch.end_alpha, frame)
        #check_set_node_parent(tree, ch.end_linear, frame)

        # Modifiers
        #frame = get_frame(tree, '__modifiers__', str(i), ch.name + ' Final Modifiers')
        #for mod in ch.modifiers:
        #    check_set_node_parent(tree, mod.frame, frame)
        pass

    clean_unused_frames(tree)

def rearrange_layer_frame_nodes(layer, tree=None):
    yp = layer.id_data.yp
    if not tree: tree = get_tree(layer)
    #nodes = tree.nodes

    # Layer channels
    for i, ch in enumerate(layer.channels):
        root_ch = yp.channels[i]

        # Modifiers
        #if len(ch.modifiers) > 0:

        #    frame = get_frame(tree, '__modifier__', str(i), root_ch.name + ' Modifiers')

        #    #check_set_node_parent(tree, ch.start_rgb, frame)
        #    #check_set_node_parent(tree, ch.start_alpha, frame)
        #    #check_set_node_parent(tree, ch.end_rgb, frame)
        #    #check_set_node_parent(tree, ch.end_alpha, frame)

        #    # Modifiers
        #    if ch.mod_group != '':
        #        check_set_node_parent(tree, ch.mod_group, frame)
        #        check_set_node_parent(tree, ch.mod_n, frame)
        #        check_set_node_parent(tree, ch.mod_s, frame)
        #        check_set_node_parent(tree, ch.mod_e, frame)
        #        check_set_node_parent(tree, ch.mod_w, frame)
        #    else:
        #        for mod in ch.modifiers:
        #            check_set_node_parent(tree, mod.frame, frame)

        #check_set_node_parent(tree, ch.linear, frame)
        #check_set_node_parent(tree, ch.source, frame)

        # Normal process

        #if root_ch.type == 'NORMAL':

            #frame = get_frame(tree, '__normal_process__', str(i), root_ch.name + ' Process')

            #check_set_node_parent(tree, ch.spread_alpha, frame)
            #check_set_node_parent(tree, ch.spread_alpha_n, frame)
            #check_set_node_parent(tree, ch.spread_alpha_s, frame)
            #check_set_node_parent(tree, ch.spread_alpha_e, frame)
            #check_set_node_parent(tree, ch.spread_alpha_w, frame)
            #check_set_node_parent(tree, ch.normal_process, frame)
            #check_set_node_parent(tree, ch.normal_flip, frame)
            #check_set_node_parent(tree, ch.height_process, frame)

        # Blend
        frame = get_frame(tree, '__blend__', str(i), root_ch.name + ' Blend')
        check_set_node_parent(tree, ch.decal_alpha, frame)
        check_set_node_parent(tree, ch.decal_alpha_n, frame)
        check_set_node_parent(tree, ch.decal_alpha_s, frame)
        check_set_node_parent(tree, ch.decal_alpha_e, frame)
        check_set_node_parent(tree, ch.decal_alpha_w, frame)
        check_set_node_parent(tree, ch.layer_intensity, frame)
        check_set_node_parent(tree, ch.intensity, frame)
        check_set_node_parent(tree, ch.extra_alpha, frame)
        check_set_node_parent(tree, ch.blend, frame)

        if root_ch.type == 'NORMAL':
            check_set_node_parent(tree, ch.spread_alpha, frame)
            #check_set_node_parent(tree, ch.spread_alpha_n, frame)
            #check_set_node_parent(tree, ch.spread_alpha_s, frame)
            #check_set_node_parent(tree, ch.spread_alpha_e, frame)
            #check_set_node_parent(tree, ch.spread_alpha_w, frame)
            
            check_set_node_parent(tree, ch.bump_distance_ignorer, frame)
            check_set_node_parent(tree, ch.tb_distance_flipper, frame)
            check_set_node_parent(tree, ch.tb_delta_calc, frame)
            check_set_node_parent(tree, ch.height_proc, frame)

            check_set_node_parent(tree, ch.height_blend, frame)
            #check_set_node_parent(tree, ch.height_blend_n, frame)
            #check_set_node_parent(tree, ch.height_blend_s, frame)
            #check_set_node_parent(tree, ch.height_blend_e, frame)
            #check_set_node_parent(tree, ch.height_blend_w, frame)

            check_set_node_parent(tree, ch.max_height_calc, frame)

            check_set_node_parent(tree, ch.normal_map_proc, frame)
            check_set_node_parent(tree, ch.normal_proc, frame)
            check_set_node_parent(tree, ch.normal_flip, frame)

            check_set_node_parent(tree, ch.vdisp_proc, frame)

            #check_set_node_parent(tree, ch.blend_height, frame)
            #check_set_node_parent(tree, ch.intensity_height, frame)
            #check_set_node_parent(tree, ch.height_process_temp, frame)
            #for d in neighbor_directions:
            #    check_set_node_parent(tree, getattr(ch, 'blend_height_' + d), frame)
            #    check_set_node_parent(tree, getattr(ch, 'intensity_height_' + d), frame)
            #    check_set_node_parent(tree, getattr(ch, 'height_process_' + d), frame)

        #check_set_node_parent(tree, ch.normal_flip, frame)
        #check_set_node_parent(tree, ch.intensity_multiplier, frame)

    # Masks
    for i, mask in enumerate(layer.masks):
        frame = get_frame(tree, '__mask__', str(i), mask.name)

        if mask.group_node != '':
            check_set_node_parent(tree, mask.group_node, frame)
        else: 
            check_set_node_parent(tree, mask.baked_source, frame)
            check_set_node_parent(tree, mask.source, frame)

        check_set_node_parent(tree, mask.uv_neighbor, frame)
        check_set_node_parent(tree, mask.uv_map, frame)

        check_set_node_parent(tree, mask.source_n, frame)
        check_set_node_parent(tree, mask.source_s, frame)
        check_set_node_parent(tree, mask.source_e, frame)
        check_set_node_parent(tree, mask.source_w, frame)

        check_set_node_parent(tree, mask.blur_vector, frame)
        check_set_node_parent(tree, mask.separate_color_channels, frame)
        check_set_node_parent(tree, mask.decal_process, frame)
        check_set_node_parent(tree, mask.decal_alpha, frame)
        check_set_node_parent(tree, mask.decal_alpha_n, frame)
        check_set_node_parent(tree, mask.decal_alpha_s, frame)
        check_set_node_parent(tree, mask.decal_alpha_e, frame)
        check_set_node_parent(tree, mask.decal_alpha_w, frame)
        check_set_node_parent(tree, mask.mapping, frame)
        check_set_node_parent(tree, mask.baked_mapping, frame)
        check_set_node_parent(tree, mask.texcoord, frame)

        for c in mask.channels:
            check_set_node_parent(tree, c.mix, frame)
            check_set_node_parent(tree, c.mix_pure, frame)
            check_set_node_parent(tree, c.mix_remains, frame)
            check_set_node_parent(tree, c.mix_limit, frame)
            check_set_node_parent(tree, c.mix_limit_normal, frame)

    clean_unused_frames(tree)

def arrange_mask_modifier_nodes(tree, mask, loc):

    for m in mask.modifiers:

        if m.type == 'INVERT':
            if check_set_node_loc(tree, m.invert, loc):
                loc.x += 170.0

        elif m.type == 'RAMP':
            if check_set_node_loc(tree, m.ramp, loc):
                loc.x += 265.0

            if check_set_node_loc(tree, m.ramp_mix, loc):
                loc.x += 170.0

        elif m.type == 'CURVE':
            if check_set_node_loc(tree, m.curve, loc):
                loc.x += 265.0

    return loc

def arrange_modifier_nodes(tree, parent, loc, is_value=False, return_y_offset=False, use_modifier_1=False):

    ori_y = loc.y
    offset_y = 0

    if check_set_node_loc(tree, MOD_TREE_START, loc):
        loc.x += 200

    #loc.y -= 35
    #if check_set_node_loc(tree, parent.start_rgb, loc):
    #    loc.y -= 35
    #else: loc.y += 35

    #if check_set_node_loc(tree, parent.start_alpha, loc):
    #    loc.x += 100
    #    loc.y = ori_y
    modifiers = parent.modifiers
    if use_modifier_1:
        modifiers = parent.modifiers_1

    # Modifier loops
    for m in reversed(modifiers):

        #loc.y -= 35
        #check_set_node_loc(tree, m.start_rgb, loc)

        #loc.y -= 35
        #check_set_node_loc(tree, m.start_alpha, loc)

        loc.y = ori_y
        loc.x += 20

        mod_y_offset = get_mod_y_offsets(m, is_value)
        if offset_y < mod_y_offset:
            offset_y = mod_y_offset

        if m.type == 'INVERT':
            if check_set_node_loc(tree, m.invert, loc):
                loc.x += 165.0

        elif m.type == 'RGB_TO_INTENSITY':
            if check_set_node_loc(tree, m.rgb2i, loc):
                loc.x += 165.0

        elif m.type == 'INTENSITY_TO_RGB':
            if check_set_node_loc(tree, m.i2rgb, loc):
                loc.x += 165.0

        elif m.type == 'OVERRIDE_COLOR':
            if check_set_node_loc(tree, m.oc, loc):
                loc.x += 165.0

        elif m.type == 'COLOR_RAMP':

            if check_set_node_loc(tree, m.color_ramp_alpha_multiply, loc):
                loc.x += 165.0

            if check_set_node_loc(tree, m.color_ramp_linear_start, loc):
                loc.x += 165.0

            if check_set_node_loc(tree, m.color_ramp, loc):
                loc.x += 265.0

            if check_set_node_loc(tree, m.color_ramp_linear, loc):
                loc.x += 165.0

            if check_set_node_loc(tree, m.color_ramp_mix_rgb, loc):
                loc.x += 165.0

            if check_set_node_loc(tree, m.color_ramp_mix_alpha, loc):
                loc.x += 165.0

        elif m.type == 'RGB_CURVE':
            if check_set_node_loc(tree, m.rgb_curve, loc):
                loc.x += 260.0

        elif m.type == 'HUE_SATURATION':
            if check_set_node_loc(tree, m.huesat, loc):
                loc.x += 175.0

        elif m.type == 'BRIGHT_CONTRAST':
            if check_set_node_loc(tree, m.brightcon, loc):
                loc.x += 165.0

        elif m.type == 'MULTIPLIER':
            if check_set_node_loc(tree, m.multiplier, loc):
                loc.x += 165.0

        elif m.type == 'MATH':
            if check_set_node_loc(tree, m.math, loc):
                loc.x += 165.0
        #loc.y -= 35
        #check_set_node_loc(tree, m.end_rgb, loc)
        #loc.y -= 35
        #check_set_node_loc(tree, m.end_alpha, loc)

        loc.y = ori_y
        loc.x += 100

    #loc.y -= 35
    #if check_set_node_loc(tree, parent.end_rgb, loc):
    #    loc.y -= 35
    #else: loc.y += 35

    #if check_set_node_loc(tree, parent.end_alpha, loc):
    #    loc.x += 100
    #    loc.y = ori_y

    if check_set_node_loc(tree, MOD_TREE_END, loc):
        loc.x += 200

    if return_y_offset:
        return loc, offset_y
    return loc

def rearrange_channel_source_tree_nodes(layer, ch):

    source_tree = get_channel_source_tree(ch, layer)

    loc = Vector((0, 0))

    if check_set_node_loc(source_tree, TREE_START, loc):
        loc.x += 180

    loc.y -= 300
    if check_set_node_loc(source_tree, ONE_VALUE, loc):
        loc.y -= 90
    check_set_node_loc(source_tree, ZERO_VALUE, loc)
        #loc.y += 390

    loc.y = 0

    #if check_set_node_loc(source_tree, layer.mapping, loc):
    #    loc.x += 380

    if check_set_node_loc(source_tree, ch.source, loc):
        loc.x += 280

    if check_set_node_loc(source_tree, ch.linear, loc):
        loc.x += 200

    check_set_node_loc(source_tree, TREE_END, loc)

def rearrange_source_tree_nodes(layer):

    source_tree = get_source_tree(layer)

    loc = Vector((0, 0))

    if check_set_node_loc(source_tree, TREE_START, loc):
        loc.x += 180

    loc.y -= 300
    if check_set_node_loc(source_tree, ONE_VALUE, loc):
        loc.y -= 90
    check_set_node_loc(source_tree, ZERO_VALUE, loc)
        #loc.y += 390

    loc.y = 0
    bookmark_x = loc.x

    #if check_set_node_loc(source_tree, layer.mapping, loc):
    #    loc.x += 380

    if check_set_node_loc(source_tree, layer.source, loc):
        loc.x += 280

    if layer.baked_source != '':
        loc.x = bookmark_x
        loy.y -= 320
        check_set_node_loc(source_tree, layer.baked_source, loc)
        loc.x += 280
        loc.y = 0

    if check_set_node_loc(source_tree, layer.divider_alpha, loc):
        loc.x += 200

    if check_set_node_loc(source_tree, layer.linear, loc):
        loc.x += 200

    if check_set_node_loc(source_tree, layer.flip_y, loc):
        loc.x += 200

    if layer.type in {'IMAGE', 'VCOL', 'MUSGRAVE'}:
        arrange_modifier_nodes(source_tree, layer, loc)
    else:
        if check_set_node_loc(source_tree, layer.mod_group, loc, True):
            mod_group = source_tree.nodes.get(layer.mod_group)
            arrange_modifier_nodes(mod_group.node_tree, layer, loc=Vector((0, 0)))
            loc.y -= 40
        if check_set_node_loc(source_tree, layer.mod_group_1, loc, True):
            loc.y += 40
            loc.x += 150

        for mg in parent.mod_groups:
            if check_set_node_loc(source_tree, mg.name, loc, True):
                loc.y += 40
        
        loc.x += 150

    check_set_node_loc(source_tree, TREE_END, loc)

def rearrange_mask_tree_nodes(mask):
    tree = get_mask_tree(mask)
    loc = Vector((0, 0))

    if check_set_node_loc(tree, TREE_START, loc):
        loc.x += 180

    #if check_set_node_loc(tree, mask.mapping, loc):
    #    loc.x += 380

    if check_set_node_loc(tree, mask.baked_source, loc):
        loc.y -= 270

    if check_set_node_loc(tree, mask.source, loc):
        loc.x += 280

    if mask.baked_source != '':
        loc.y = 0

    if check_set_node_loc(tree, mask.linear, loc):
        loc.x += 180
    
    if check_set_node_loc(tree, mask.separate_color_channels, loc):
        loc.x += 180

    arrange_mask_modifier_nodes(tree, mask, loc)

    if check_set_node_loc(tree, TREE_END, loc):
        loc.x += 180

def rearrange_transition_bump_nodes(tree, ch, loc):
    # Bump

    ori_x = loc.x

    #if check_set_node_loc(tree, ch.tb_bump, loc):
    #    loc.x += 170.0

    #if check_set_node_loc(tree, ch.tb_bump_flip, loc):
    #    loc.x += 170.0

    #tb_falloff_n = tree.nodes.get(ch.tb_falloff_n)
    #
    #if tb_falloff_n:

    #    if check_set_node_loc(tree, ch.tb_falloff, loc, True):
    #        loc.y -= 40
    #    if check_set_node_loc(tree, ch.tb_falloff_n, loc, True):
    #        loc.y -= 40
    #    if check_set_node_loc(tree, ch.tb_falloff_s, loc, True):
    #        loc.y -= 40
    #    if check_set_node_loc(tree, ch.tb_falloff_e, loc, True):
    #        loc.y -= 40
    #    if check_set_node_loc(tree, ch.tb_falloff_w, loc, True):
    #        loc.y -= 40
    #else:
    #    if check_set_node_loc(tree, ch.tb_falloff, loc):
    #        loc.y -= 150

    if check_set_node_loc(tree, ch.tb_inverse, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.tb_intensity_multiplier, loc):
        loc.x += 170.0

    save_x = loc.x
    loc.x = ori_x

    loc.y -= 170

    if check_set_node_loc(tree, ch.tb_falloff, loc):
        loc.y -= 150

    #if check_set_node_loc(tree, ch.tb_blend, loc):
    #    loc.x += 200.0

    #save_x = loc.x
    #loc.x = ori_x

    #loc.y -= 300.0
    #if not check_set_node_loc(tree, ch.tb_crease, loc):
    #    loc.y += 300.0

    #loc.x += 200
    #check_set_node_loc(tree, ch.tb_crease_flip, loc)

    loc.x = save_x

#def rearrange_normal_process_nodes(tree, ch, loc):
#
#    bookmark_x = loc.x
#
#    if check_set_node_loc(tree, ch.spread_alpha, loc):
#        loc.x += 200
#
#    if check_set_node_loc(tree, ch.height_process, loc):
#        loc.x += 200
#        loc.y -= 330
#
#    farthest_x = loc.x
#    bookmark_y = loc.y
#    loc.x = bookmark_x
#
#    loc.y -= 40
#    if check_set_node_loc(tree, ch.spread_alpha_n, loc, hide=True):
#        loc.y -= 40
#    else: loc.y += 40
#
#    if check_set_node_loc(tree, ch.spread_alpha_s, loc, hide=True):
#        loc.y -= 40
#
#    if check_set_node_loc(tree, ch.spread_alpha_e, loc, hide=True):
#        loc.y -= 40
#
#    if check_set_node_loc(tree, ch.spread_alpha_w, loc, hide=True):
#        loc.y = bookmark_y
#        loc.x += 200
#
#    if check_set_node_loc(tree, ch.normal_process, loc):
#        loc.x += 200
#
#    if check_set_node_loc(tree, ch.normal_flip, loc):
#        loc.x += 200
#
#    if loc.x < farthest_x: 
#        loc.x = farthest_x

def rearrange_layer_nodes(layer, tree=None):
    yp = layer.id_data.yp

    if yp.halt_reconnect: return

    if not tree: tree = get_tree(layer)
    nodes = tree.nodes

    #print('Rearrange layer ' + layer.name)

    #start = nodes.get(layer.start)
    #end = nodes.get(layer.end)

    # Get transition bump channel
    flip_bump = False
    chain = -1
    bump_ch = get_transition_bump_channel(layer)
    if bump_ch:
        flip_bump = bump_ch.transition_bump_flip #or layer.type == 'BACKGROUND'
        #flip_bump = bump_ch.transition_bump_flip
        chain = min(len(layer.masks), bump_ch.transition_bump_chain)

    # Back to source nodes
    loc = Vector((0, 0))

    # Start node
    check_set_node_loc(tree, TREE_START, loc)

    start = tree.nodes.get(TREE_START)
    check_set_node_width(start, 250)

    if start: loc.y = -(len(start.outputs) * 25)

    cache_found = False

    # Layer Caches
    if check_set_node_loc(tree, layer.cache_image, loc, hide=False):
        loc.y -= 270
        cache_found = True

    if check_set_node_loc(tree, layer.cache_vcol, loc, hide=False):
        loc.y -= 200
        cache_found = True

    if check_set_node_loc(tree, layer.cache_color, loc, hide=False):
        loc.y -= 200
        cache_found = True

    if check_set_node_loc(tree, layer.cache_brick, loc, hide=False):
        loc.y -= 400
        cache_found = True

    if check_set_node_loc(tree, layer.cache_checker, loc, hide=False):
        loc.y -= 170
        cache_found = True

    if check_set_node_loc(tree, layer.cache_gradient, loc, hide=False):
        loc.y -= 140
        cache_found = True

    if check_set_node_loc(tree, layer.cache_magic, loc, hide=False):
        loc.y -= 180
        cache_found = True

    if check_set_node_loc(tree, layer.cache_musgrave, loc, hide=False):
        loc.y -= 270
        cache_found = True

    if check_set_node_loc(tree, layer.cache_noise, loc, hide=False):
        loc.y -= 170
        cache_found = True

    if check_set_node_loc(tree, layer.cache_voronoi, loc, hide=False):
        loc.y -= 170
        cache_found = True

    if check_set_node_loc(tree, layer.cache_gabor, loc, hide=False):
        loc.y -= 170
        cache_found = True

    if check_set_node_loc(tree, layer.cache_wave, loc, hide=False):
        loc.y -= 260
        cache_found = True

    # Channel Caches
    for ch in layer.channels:

        if check_set_node_loc(tree, ch.cache_ramp, loc, hide=False):
            loc.y -= 250
            cache_found = True

        if check_set_node_loc(tree, ch.cache_falloff_curve, loc, hide=False):
            loc.y -= 270
            cache_found = True

        if check_set_node_loc(tree, ch.cache_image, loc, hide=False):
            loc.y -= 270
            cache_found = True

        if check_set_node_loc(tree, ch.cache_vcol, loc, hide=False):
            loc.y -= 200
            cache_found = True

        if check_set_node_loc(tree, ch.cache_brick, loc, hide=False):
            loc.y -= 400
            cache_found = True

        if check_set_node_loc(tree, ch.cache_checker, loc, hide=False):
            loc.y -= 170
            cache_found = True

        if check_set_node_loc(tree, ch.cache_gradient, loc, hide=False):
            loc.y -= 140
            cache_found = True

        if check_set_node_loc(tree, ch.cache_magic, loc, hide=False):
            loc.y -= 180
            cache_found = True

        if check_set_node_loc(tree, ch.cache_musgrave, loc, hide=False):
            loc.y -= 270
            cache_found = True

        if check_set_node_loc(tree, ch.cache_noise, loc, hide=False):
            loc.y -= 170
            cache_found = True

        if check_set_node_loc(tree, ch.cache_voronoi, loc, hide=False):
            loc.y -= 170
            cache_found = True

        if check_set_node_loc(tree, ch.cache_gabor, loc, hide=False):
            loc.y -= 170
            cache_found = True

        if check_set_node_loc(tree, ch.cache_wave, loc, hide=False):
            loc.y -= 260
            cache_found = True

        if check_set_node_loc(tree, ch.cache_1_image, loc, hide=False):
            loc.y -= 270
            cache_found = True

    # Mask caches
    for mask in layer.masks:

        if check_set_node_loc(tree, mask.cache_modifier_ramp, loc, hide=False, parent_unset=True):
            loc.y -= 250
            cache_found = True

        if check_set_node_loc(tree, mask.cache_modifier_curve, loc, hide=False, parent_unset=True):
            loc.y -= 270
            cache_found = True

        if check_set_node_loc(tree, mask.cache_image, loc, hide=False, parent_unset=True):
            loc.y -= 270
            cache_found = True

        if check_set_node_loc(tree, mask.cache_vcol, loc, hide=False, parent_unset=True):
            loc.y -= 200
            cache_found = True

        if check_set_node_loc(tree, mask.cache_brick, loc, hide=False, parent_unset=True):
            loc.y -= 400
            cache_found = True

        if check_set_node_loc(tree, mask.cache_checker, loc, hide=False, parent_unset=True):
            loc.y -= 170
            cache_found = True

        if check_set_node_loc(tree, mask.cache_gradient, loc, hide=False, parent_unset=True):
            loc.y -= 140
            cache_found = True

        if check_set_node_loc(tree, mask.cache_magic, loc, hide=False, parent_unset=True):
            loc.y -= 180
            cache_found = True

        if check_set_node_loc(tree, mask.cache_musgrave, loc, hide=False, parent_unset=True):
            loc.y -= 270
            cache_found = True

        if check_set_node_loc(tree, mask.cache_noise, loc, hide=False, parent_unset=True):
            loc.y -= 170
            cache_found = True

        if check_set_node_loc(tree, mask.cache_voronoi, loc, hide=False, parent_unset=True):
            loc.y -= 170
            cache_found = True

        if check_set_node_loc(tree, mask.cache_gabor, loc, hide=False, parent_unset=True):
            loc.y -= 170
            cache_found = True

        if check_set_node_loc(tree, mask.cache_wave, loc, hide=False, parent_unset=True):
            loc.y -= 260
            cache_found = True

    if cache_found or start: loc.x += 350
    if start: loc.y = -(len(start.outputs) * 40)
    else: loc.y = 0

    # Arrange pack unpack height group
    if layer.type == 'GROUP':
        for i, ch in enumerate(layer.channels):
            root_ch = yp.channels[i] 
            if root_ch.type == 'NORMAL':

                if check_set_node_loc(tree, ch.height_group_unpack, loc):
                    loc.y -= 250
                if check_set_node_loc(tree, ch.height_alpha_group_unpack, loc):
                    loc.y -= 250

    if layer.source_group != '' and check_set_node_loc(tree, layer.source_group, loc, hide=True):
        rearrange_source_tree_nodes(layer)
        loc.y -= 40

    else:
        if check_set_node_loc(tree, layer.flip_y, loc, hide=False):
            loc.y -= 140

        if check_set_node_loc(tree, layer.linear, loc, hide=False):
            loc.y -= 140

        if check_set_node_loc(tree, layer.divider_alpha, loc, hide=False):
            loc.y -= 250

        if check_set_node_loc(tree, layer.source, loc, hide=False):
            if layer.type == 'BRICK':
                loc.y -= 400
            elif layer.type == 'CHECKER':
                loc.y -= 170
            elif layer.type == 'GRADIENT':
                loc.y -= 140
            elif layer.type == 'MAGIC':
                loc.y -= 180
            elif layer.type == 'MUSGRAVE':
                loc.y -= 270
            elif layer.type == 'NOISE':
                loc.y -= 170
            elif layer.type == 'GABOR':
                loc.y -= 170
            elif layer.type == 'VORONOI':
                loc.y -= 190
            else:
                loc.y -= 320

    if check_set_node_loc(tree, layer.baked_source, loc, hide=False):
        loc.y -= 320

    if check_set_node_loc(tree, layer.source_n, loc, hide=True):
        loc.y -= 40

    if check_set_node_loc(tree, layer.source_s, loc, hide=True):
        loc.y -= 40

    if check_set_node_loc(tree, layer.source_e, loc, hide=True):
        loc.y -= 40

    if check_set_node_loc(tree, layer.source_w, loc, hide=True):
        loc.y -= 40

    if check_set_node_loc(tree, layer.uv_neighbor, loc):
        loc.y -= 260

    if check_set_node_loc(tree, layer.uv_neighbor_1, loc):
        loc.y -= 260

    for ch in layer.channels:
        if ch.source_group != '' and check_set_node_loc(tree, ch.source_group, loc, hide=True):
            rearrange_channel_source_tree_nodes(layer, ch)
            loc.y -= 40
        else:
            if check_set_node_loc(tree, ch.source, loc, hide=False):
                if ch.override_type == 'BRICK':
                    loc.y -= 400
                elif ch.override_type == 'CHECKER':
                    loc.y -= 170
                elif ch.override_type == 'GRADIENT':
                    loc.y -= 140
                elif ch.override_type == 'MAGIC':
                    loc.y -= 180
                elif ch.override_type == 'MUSGRAVE':
                    loc.y -= 270
                elif ch.override_type == 'NOISE':
                    loc.y -= 170
                elif ch.override_type == 'GABOR':
                    loc.y -= 170
                elif ch.override_type == 'VORONOI':
                    loc.y -= 190
                else:
                    loc.y -= 260

        if check_set_node_loc(tree, ch.source_n, loc, hide=True):
            loc.y -= 40

        if check_set_node_loc(tree, ch.source_s, loc, hide=True):
            loc.y -= 40

        if check_set_node_loc(tree, ch.source_e, loc, hide=True):
            loc.y -= 40

        if check_set_node_loc(tree, ch.source_w, loc, hide=True):
            loc.y -= 40

        if check_set_node_loc(tree, ch.source_1, loc, hide=False):
            if ch.override_1_type == 'DEFAULT':
                loc.y -= 190
            else:
                loc.y -= 260

        if check_set_node_loc(tree, ch.uv_neighbor, loc):
            loc.y -= 260

    #if layer.source_group == '' and check_set_node_loc(tree, layer.mapping, loc):
    if check_set_node_loc(tree, layer.mapping, loc):
        loc.y -= 430

    if check_set_node_loc(tree, layer.baked_mapping, loc):
        loc.y -= 360

    if check_set_node_loc(tree, layer.blur_vector, loc):
        loc.y -= 140

    if check_set_node_loc(tree, layer.uv_map, loc):
        loc.y -= 120

    #if check_set_node_loc(tree, layer.tangent_flip, loc):
    #    loc.y -= 120

    #if check_set_node_loc(tree, layer.bitangent_flip, loc):
    #    loc.y -= 120

    #if check_set_node_loc(tree, layer.tangent, loc):
    #    loc.y -= 160

    #if check_set_node_loc(tree, layer.bitangent, loc):
    #    loc.y -= 160

    if layer.type == 'GROUP':
        loc.y -= 500

    if check_set_node_loc(tree, ONE_VALUE, loc):
        loc.y -= 90

    if check_set_node_loc(tree, ZERO_VALUE, loc):
        loc.y -= 90

    if check_set_node_loc(tree, GEOMETRY, loc):
        loc.y -= 240

    #if check_set_node_loc(tree, TEXCOORD, loc):
    #    loc.y -= 240

    if check_set_node_loc(tree, layer.decal_process, loc):
        loc.y -= 170

    if check_set_node_loc(tree, layer.texcoord, loc):
        loc.y -= 240

    #if check_set_node_loc(tree, TREE_START, loc):
    #    loc.y -= 240

    if check_set_node_loc(tree, layer.bump_process, loc):
        loc.y -= 300

    loc.x += 350
    loc.y = 0

    # Layer modifiers
    if layer.source_group == '':
        '''
        if layer.mod_group != '':
        '''
        if len(layer.mod_groups) > 0:
            '''
            mod_group = nodes.get(layer.mod_group)
            arrange_modifier_nodes(mod_group.node_tree, layer, loc.copy())
            check_set_node_loc(tree, layer.mod_group, loc, hide=True)
            loc.y -= 40
            check_set_node_loc(tree, layer.mod_group_1, loc, hide=True)
            loc.y += 40
            '''
            mod_group = nodes.get(layer.mod_groups[0].name)
            if mod_group: arrange_modifier_nodes(mod_group.node_tree, layer, loc.copy())
            for mg in layer.mod_groups:
                if check_set_node_loc(tree, mg.name, loc, True):
                    loc.y -= 40
            loc.x += 200
        else:
            loc = arrange_modifier_nodes(tree, layer, loc)

    start_x = loc.x
    farthest_x = 0
    bookmarks_ys = []

    for i, ch in enumerate(layer.channels):

        root_ch = yp.channels[i]

        if root_ch.type == 'NORMAL':
            chain = min(len(layer.masks), ch.transition_bump_chain)
        elif bump_ch:
            chain = min(len(layer.masks), bump_ch.transition_bump_chain)
        else:
            chain = -1

        loc.x = start_x
        bookmark_y = loc.y
        bookmarks_ys.append(bookmark_y)
        offset_y = NO_MODIFIER_Y_OFFSET
        #offset_y = 0

        #if check_set_node_loc(tree, ch.source, loc):
        #    loc.x += 200

        if ch.source_group == '':
            if check_set_node_loc(tree, ch.linear, loc):
                loc.x += 200

        # Modifier loop
        if ch.mod_group != '':
            mod_group = nodes.get(ch.mod_group)
            arrange_modifier_nodes(mod_group.node_tree, ch, Vector((0, 0)))
            check_set_node_loc(tree, ch.mod_group, loc, hide=True)
            loc.y -= 40
        else:
            loc, mod_offset_y = arrange_modifier_nodes(
                tree, ch, loc, is_value=root_ch.type == 'VALUE',
                return_y_offset = True
            )

            if offset_y < mod_offset_y:
                offset_y = mod_offset_y

        if check_set_node_loc(tree, ch.mod_n, loc, hide=True):
            loc.y -= 40

        if check_set_node_loc(tree, ch.mod_s, loc, hide=True):
            loc.y -= 40

        if check_set_node_loc(tree, ch.mod_e, loc, hide=True):
            loc.y -= 40

        if check_set_node_loc(tree, ch.mod_w, loc, hide=True):
            loc.y = bookmark_y
            loc.x += 160

        bookmark_x1 = loc.x

        linear_1 = nodes.get(ch.linear_1)
        if linear_1:
            loc.x = start_x
            loc.y -= offset_y
            offset_y = 0
            check_set_node_loc(tree, ch.linear_1, loc)
            loc.x += 200

        flip_y = nodes.get(ch.flip_y)
        if flip_y:
            if not linear_1:
                loc.x = start_x
                loc.y -= offset_y
                offset_y = 0
            check_set_node_loc(tree, ch.flip_y, loc)
            loc.x += 200

        if len(ch.modifiers_1) > 0:
            if not linear_1: 
                loc.x = start_x
                loc.y -= offset_y

            loc, mod_offset_y = arrange_modifier_nodes(
                tree, ch, loc, is_value=root_ch.type == 'VALUE',
                return_y_offset=True, use_modifier_1=True
            )

            offset_y = mod_offset_y

        if loc.x < bookmark_x1:
            loc.x = bookmark_x1

        #if bump_ch or chain == 0:
        #    rearrange_normal_process_nodes(tree, ch, loc)

        if loc.x > farthest_x: farthest_x = loc.x

        if root_ch.type == 'NORMAL': #and ch.normal_map_type == 'FINE_BUMP_MAP' and offset_y < FINE_BUMP_Y_OFFSET:
            if offset_y < FINE_BUMP_Y_OFFSET:
                offset_y = FINE_BUMP_Y_OFFSET

        loc.y -= offset_y

        # If next channel had modifier
        if i+1 < len(layer.channels):
            next_ch = layer.channels[i + 1]
            if len(next_ch.modifiers) > 0 and next_ch.mod_group == '':
                loc.y -= 35

    if bookmarks_ys:
        mid_y = (bookmarks_ys[-1]) / 2
    else: mid_y = 0

    y_step = 200
    y_mid = -(len(layer.channels) * y_step / 2)

    if bump_ch and chain == 0:

        loc.x = farthest_x
        loc.y = 0
        bookmark_x = loc.x

        for i, ch in enumerate(layer.channels):

            loc.x = bookmark_x

            if check_set_node_loc(tree, ch.intensity_multiplier, loc, False):
                loc.y -= 200

            if flip_bump and check_set_node_loc(tree, ch.tao, loc, False):
                loc.y -= 230

            if ch.enable_transition_ramp:
                if check_set_node_loc(tree, ch.tr_ramp, loc):
                    loc.y -= 230

            # Transition bump
            if ch == bump_ch:
                rearrange_transition_bump_nodes(tree, bump_ch, loc)
                loc.y -= 300

            if loc.x > farthest_x: farthest_x = loc.x
            #loc.y -= y_step

    loc.x = farthest_x
    loc.y = 0
    bookmark_x = loc.x

    # Masks
    for i, mask in enumerate(layer.masks):

        loc.y = 0
        loc.x = farthest_x

        if check_set_node_loc(tree, mask.decal_alpha, loc, True):
            loc.y -= 40

        if check_set_node_loc(tree, mask.decal_alpha_n, loc, True):
            loc.y -= 40

        if check_set_node_loc(tree, mask.decal_alpha_s, loc, True):
            loc.y -= 40

        if check_set_node_loc(tree, mask.decal_alpha_e, loc, True):
            loc.y -= 40

        if check_set_node_loc(tree, mask.decal_alpha_w, loc, True):
            loc.y -= 40

        if mask.group_node != '' and check_set_node_loc(tree, mask.group_node, loc, True):
            rearrange_mask_tree_nodes(mask)
            loc.y -= 40

        else:
            if check_set_node_loc(tree, mask.linear, loc):
                loc.y -= 140

            if check_set_node_loc(tree, mask.baked_source, loc):
                loc.y -= 270

            if check_set_node_loc(tree, mask.source, loc):
                loc.y -= 270

        if check_set_node_loc(tree, mask.source_n, loc, True):
            loc.y -= 40

        if check_set_node_loc(tree, mask.source_s, loc, True):
            loc.y -= 40

        if check_set_node_loc(tree, mask.source_e, loc, True):
            loc.y -= 40

        if check_set_node_loc(tree, mask.source_w, loc, True):
            loc.y -= 40

        if check_set_node_loc(tree, mask.uv_neighbor, loc):
            loc.y -= 320

        #if mask.group_node == '' and check_set_node_loc(tree, mask.mapping, loc):
        if check_set_node_loc(tree, mask.mapping, loc):
            loc.y -= 360

        if check_set_node_loc(tree, mask.baked_mapping, loc):
            loc.y -= 360

        if check_set_node_loc(tree, mask.blur_vector, loc):
            loc.y -= 140

        if check_set_node_loc(tree, mask.decal_process, loc):
            loc.y -= 170

        if check_set_node_loc(tree, mask.uv_map, loc):
            loc.y -= 130

        if check_set_node_loc(tree, mask.texcoord, loc):
            loc.y -= 170

        #if check_set_node_loc(tree, mask.tangent_flip, loc):
        #    loc.y -= 120

        #if check_set_node_loc(tree, mask.bitangent_flip, loc):
        #    loc.y -= 120

        #if check_set_node_loc(tree, mask.tangent, loc):
        #    loc.y -= 170

        #if check_set_node_loc(tree, mask.bitangent, loc):
        #    loc.y -= 180

        loc.y = 0

        loc.x += 270
        check_set_node_loc(tree, mask.separate_color_channels, loc)

        if mask.group_node == '' and len(mask.modifiers) > 0:
            loc.x += 270
            arrange_mask_modifier_nodes(tree, mask, loc)
            loc.x += 20
        else:
            loc.x += 370

        bookmark_x = loc.x

        if check_set_node_loc(tree, mask.mix, loc, True):
            loc.y -= 40

        # Mask channels
        for j, c in enumerate(mask.channels):

            ch = layer.channels[j]
            root_ch = yp.channels[j]

            if root_ch.type == 'NORMAL':
                chain = min(len(layer.masks), ch.transition_bump_chain)
            elif bump_ch:
                chain = min(len(layer.masks), bump_ch.transition_bump_chain)
            else:
                chain = -1

            loc.x = bookmark_x
            bookmark_y = loc.y

            mix_pure = tree.nodes.get(c.mix_pure)
            mix_remains = tree.nodes.get(c.mix_remains)
            mix_normal = tree.nodes.get(c.mix_normal)
            mix_limit_normal = tree.nodes.get(c.mix_limit_normal)

            if mix_pure or mix_remains or mix_normal or mix_limit_normal:

                if check_set_node_loc(tree, c.mix, loc, True):
                    loc.y -= 40

                if check_set_node_loc(tree, c.mix_pure, loc, True):
                    loc.y -= 40

                if check_set_node_loc(tree, c.mix_remains, loc, True):
                    loc.y -= 40

                if check_set_node_loc(tree, c.mix_normal, loc, True):
                    loc.y -= 40

                if check_set_node_loc(tree, c.mix_limit_normal, loc, True):
                    loc.y -= 40

            if check_set_node_loc(tree, c.mix, loc):
                if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump:
                    if layer.type == 'GROUP' and mask.blend_type in limited_mask_blend_types:
                        loc.y -= 540.0
                    else:
                        loc.y -= 430.0
                else:
                    loc.y -= 240.0

            if check_set_node_loc(tree, c.mix_limit, loc, True):
                loc.y -= 40

            loc.x += 230

            bookmark_y1 = loc.y
            loc.y = bookmark_y

            # Transition effects
            if i == chain-1 and bump_ch:

                ch = layer.channels[j]

                if check_set_node_loc(tree, ch.intensity_multiplier, loc, False):
                    loc.y -= 200

                if flip_bump and check_set_node_loc(tree, ch.tao, loc, False):
                    loc.y -= 230

                #if not flip_bump and ch.enable and ch.enable_transition_ramp:
                if ch.enable_transition_ramp and (
                    (not ch.transition_ramp_intensity_unlink or flip_bump or ch.transition_ramp_blend_type != 'MIX') #or
                    and not (layer.parent_idx != -1 and layer.type == 'BACKGROUND' and ch.transition_ramp_blend_type == 'MIX')
                        ):
                    if check_set_node_loc(tree, ch.tr_ramp, loc):
                        loc.y -= 230

                if bump_ch == ch:
                    rearrange_transition_bump_nodes(tree, ch, loc)
                    loc.y -= 300

                #if not bump_ch:
                #    rearrange_normal_process_nodes(tree, ch, loc)
                #    loc.y -= 300

            else:
                loc.y = bookmark_y1

            #if i == len(layer.masks)-1:

            #    if root_ch.type == 'NORMAL':
            #        loc.y = bookmark_y

            #        rearrange_normal_process_nodes(tree, ch, loc)
            #        loc.y -= 300

            if loc.x > farthest_x: farthest_x = loc.x

    loc.x = farthest_x
    loc.y = 0
    bookmark_x = loc.x

    for i, ch in enumerate(layer.channels):

        loc.x = bookmark_x

        # Transition ramp
        if not bump_ch and ch.enable_transition_ramp:
            if check_set_node_loc(tree, ch.tr_ramp, loc):
                loc.x += 200

        # Leftover ramp node
        #if not ch.enable_transition_ramp and check_set_node_loc(tree, ch.tr_ramp, loc):
        #    loc.x += 270.0

        # Transition bump
        #rearrange_transition_bump_nodes(tree, ch, loc)

        if loc.x > farthest_x: farthest_x = loc.x
        loc.y -= y_step

    #loc.x += 200
    loc.x = farthest_x
    #loc.y = y_mid
    loc.y = 0

    # Start node
    #check_set_node_loc(tree, TREE_START, loc)

    #start = tree.nodes.get(TREE_START)
    #check_set_node_width(start, 250)

    #loc.x += 300
    #loc.y = 0

    #bookmark_x = loc.x

    #for i, ch in enumerate(layer.channels):

    #    root_ch = yp.channels[i]

    #    if root_ch.type == 'NORMAL':

    #        rearrange_normal_process_nodes(tree, ch, loc)
    #        loc.y -= 300
    #        loc.x += 30
    #    else:
    #        loc.y -= y_step

    #    if loc.x > farthest_x: farthest_x = loc.x

    loc.y = 0
    bookmark_x = loc.x

    # Channel blends
    for i, ch in enumerate(layer.channels):

        root_ch = yp.channels[i]

        loc.x = bookmark_x
        #loc.y = bookmarks_ys[i]

        y_offset = 240

        #if ch != bump_ch or (ch == bump_ch and chain == len(layer.masks)):
        #    if check_set_node_loc(tree, ch.intensity_multiplier, loc):
        #        loc.x += 200.0

        if not flip_bump and check_set_node_loc(tree, ch.tao, loc):
            loc.x += 200
            y_offset += 120

        # Flipped transition ramp
        if bump_ch and flip_bump:
            if check_set_node_loc(tree, ch.tr_ramp_blend, loc):
                loc.x += 200
                y_offset += 90

        if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump and layer.texcoord_type == 'Decal':

            ori_y = loc.y

            if check_set_node_loc(tree, ch.decal_alpha, loc, True):
                loc.y -= 40

            if check_set_node_loc(tree, ch.decal_alpha_n, loc, True):
                loc.y -= 40

            if check_set_node_loc(tree, ch.decal_alpha_s, loc, True):
                loc.y -= 40

            if check_set_node_loc(tree, ch.decal_alpha_e, loc, True):
                loc.y -= 40

            if check_set_node_loc(tree, ch.decal_alpha_w, loc, True):
                loc.y -= 40
            
            loc.x += 200
            loc.y = ori_y

        elif check_set_node_loc(tree, ch.decal_alpha, loc):
            loc.x += 200

        if check_set_node_loc(tree, ch.layer_intensity, loc):
            loc.x += 200

        if root_ch.type == 'NORMAL':
            save_y = loc.y
            #spread_alpha = tree.nodes.get(ch.spread_alpha)
            #spread_alpha_n = tree.nodes.get(ch.spread_alpha_n)

            #if spread_alpha_n:
            #    if check_set_node_loc(tree, ch.spread_alpha, loc, True):
            #        loc.y -= 40

            #    if check_set_node_loc(tree, ch.spread_alpha_n, loc, True):
            #        loc.y -= 40

            #    if check_set_node_loc(tree, ch.spread_alpha_s, loc, True):
            #        loc.y -= 40

            #    if check_set_node_loc(tree, ch.spread_alpha_e, loc, True):
            #        loc.y -= 40

            #    if check_set_node_loc(tree, ch.spread_alpha_w, loc, True):
            #        loc.y -= 40

            #    loc.y = save_y
            #    loc.x += 200

            if check_set_node_loc(tree, ch.bump_distance_ignorer, loc):
                loc.x += 200

            if check_set_node_loc(tree, ch.tb_distance_flipper, loc):
                loc.x += 200

            if check_set_node_loc(tree, ch.tb_delta_calc, loc):
                loc.x += 200

            #elif spread_alpha:
            if check_set_node_loc(tree, ch.spread_alpha, loc):
                loc.x += 200

            if check_set_node_loc(tree, ch.height_proc, loc):
                loc.x += 200

            #if check_set_node_loc(tree, ch.height_blend, loc):
            #    loc.x += 200
            save_y = loc.y
            #height_blend = tree.nodes.get(ch.height_blend)
            #height_blend_n = tree.nodes.get(ch.height_blend_n)

            #if height_blend_n:
            #    if check_set_node_loc(tree, ch.height_blend, loc, True):
            #        loc.y -= 40

            #    if check_set_node_loc(tree, ch.height_blend_n, loc, True):
            #        loc.y -= 40

            #    if check_set_node_loc(tree, ch.height_blend_s, loc, True):
            #        loc.y -= 40

            #    if check_set_node_loc(tree, ch.height_blend_e, loc, True):
            #        loc.y -= 40

            #    if check_set_node_loc(tree, ch.height_blend_w, loc, True):
            #        loc.y -= 40

            #    loc.y = save_y
            #    loc.x += 200

            #elif height_blend:
            if check_set_node_loc(tree, ch.height_blend, loc):
                loc.x += 200

            if check_set_node_loc(tree, ch.max_height_calc, loc):
                loc.x += 200

            if check_set_node_loc(tree, ch.normal_map_proc, loc):
                loc.x += 200

            if check_set_node_loc(tree, ch.normal_proc, loc):
                loc.x += 200

            if check_set_node_loc(tree, ch.normal_flip, loc):
                loc.x += 200

            if check_set_node_loc(tree, ch.vdisp_flip_yz, loc):
                loc.x += 200

            if check_set_node_loc(tree, ch.vdisp_proc, loc):
                loc.x += 200

        if check_set_node_loc(tree, ch.intensity, loc):
            loc.x += 200

        bookmark_x1 = loc.x

        if (
                (ch.enable_transition_ramp and not flip_bump and ch.transition_ramp_intensity_unlink 
                and ch.transition_ramp_blend_type == 'MIX') or
                (layer.parent_idx != -1 and layer.type == 'BACKGROUND' and ch.transition_ramp_blend_type == 'MIX')
            ):
            if check_set_node_loc(tree, ch.tr_ramp, loc):
                loc.x += 200
                #y_offset += 60

        #save_y = loc.y
        #save_x = loc.x

        #loc.y = save_y
        #if loc.x < save_x:
        #    loc.x = save_x

        if check_set_node_loc(tree, ch.extra_alpha, loc):
            loc.x += 200

        if check_set_node_loc(tree, ch.blend, loc):
            loc.x += 250

        #loc.y -= 170
        #loc.x = bookmark_x1
        #loc.x = bookmark_x

        #if root_ch.enable_smooth_bump:

            #save_y = loc.y

            #if check_set_node_loc(tree, ch.height_process_temp, loc, True):
            #    loc.y -= 60

            #for d in neighbor_directions:
            #    if check_set_node_loc(tree, getattr(ch, 'height_process_' + d), loc, True):
            #        loc.y -= 60

            #loc.y = save_y
            #loc.x += 200

            #if check_set_node_loc(tree, ch.intensity_height, loc, True):
            #    loc.y -= 40

            #for d in neighbor_directions:
            #    if check_set_node_loc(tree, getattr(ch, 'intensity_height_' + d), loc, True):
            #        loc.y -= 40

            #loc.y = save_y
            #loc.x += 200

            #if check_set_node_loc(tree, ch.blend_height, loc, True):
            #    loc.y -= 40

            #for d in neighbor_directions:
            #    if check_set_node_loc(tree, getattr(ch, 'blend_height_' + d), loc, True):
            #        loc.y -= 40

            #loc.x += 250
        #else:
            #if check_set_node_loc(tree, ch.height_process_temp, loc):
            #    loc.x += 200

            #if check_set_node_loc(tree, ch.intensity_height, loc):
            #    loc.x += 200

            #if check_set_node_loc(tree, ch.blend_height, loc):
            #    loc.x += 250
            #pass

        if loc.x > farthest_x: farthest_x = loc.x

        #loc.y -= y_step
        #loc.y -= 240
        loc.y -= y_offset

    loc.x = farthest_x
    #loc.y = mid_y
    #loc.y = y_mid
    loc.y = 0

    check_set_node_loc(tree, TREE_END, loc)

    rearrange_layer_frame_nodes(layer, tree)

def rearrange_relief_mapping_nodes(group_tree):
    parallax_ch = get_root_parallax_channel(group_tree.yp)
    if not parallax_ch: return

    baked_parallax = group_tree.nodes.get(BAKED_PARALLAX)
    if baked_parallax:
        linear_loop = baked_parallax.node_tree.nodes.get('_linear_search')
        if linear_loop:
            tree = linear_loop.node_tree
            
            loc = Vector((0,0))
            check_set_node_loc(tree, TREE_START, loc)

            loc.x += 200

            for i in range(parallax_ch.parallax_num_of_linear_samples):
                if check_set_node_loc(tree, '_iterate_' + str(i), loc):
                    loc.x += 200

            check_set_node_loc(tree, TREE_END, loc)

        binary_loop = baked_parallax.node_tree.nodes.get('_binary_search')
        if binary_loop:
            tree = binary_loop.node_tree
            
            loc = Vector((0,0))
            check_set_node_loc(tree, TREE_START, loc)

            loc.x += 200

            for i in range(parallax_ch.parallax_num_of_binary_samples):
                if check_set_node_loc(tree, '_iterate_' + str(i), loc):
                    loc.x += 200

            check_set_node_loc(tree, TREE_END, loc)

def rearrange_parallax_iteration(tree, prefix): #, iter_count):
    loc = Vector((0,0))
    check_set_node_loc(tree, TREE_START, loc)

    loc.x += 200

    #for i in range(iter_count):
    i = 0
    while True:
        if check_set_node_loc(tree, prefix + str(i), loc):
            loc.x += 200
        else: break
        i += 1

    check_set_node_loc(tree, TREE_END, loc)

def rearrange_parallax_depth_group(tree):
    loc = Vector((0,0))

    iterate = tree.nodes.get('_iterate')
    loc.x = iterate.location.x
    loc.y = iterate.location.y - 400

    counter = 0
    while True:
        if check_set_node_loc(tree, '_iterate_depth_' + str(counter), loc):
            idp = tree.nodes.get('_iterate_depth_' + str(counter))
            rearrange_parallax_iteration(idp.node_tree, '_iterate_') #, PARALLAX_DIVIDER)
            loc.y -= 400
            counter += 1
        else:
            break

def rearrange_parallax_layer_nodes_(yp, parallax):
    parallax_ch = get_root_parallax_channel(yp)
    if not parallax_ch: return

    #print('Par', parallax.name)

    loop = parallax.node_tree.nodes.get('_parallax_loop')
    if loop:
        #top_level_count = calculate_parallax_top_level_count(int(parallax_ch.parallax_num_of_layers))
        rearrange_parallax_iteration(loop.node_tree, '_iterate_') #, top_level_count)

        #group_needed = calculate_group_needed(parallax_ch.parallax_num_of_layers)
        #rearrange_parallax_iteration(loop.node_tree, '_iterate_group_', group_needed)

        #iterate_group_0 = loop.node_tree.nodes.get('_iterate_group_0')
        #if iterate_group_0:
        #    rearrange_parallax_iteration(iterate_group_0.node_tree, '_iterate_', PARALLAX_DIVIDER)

        # Rearrange parallax depth group source
        rearrange_parallax_depth_group(loop.node_tree)

#def rearrange_parallax_layer_nodes(yp, parallax):
#    parallax_ch = get_root_parallax_channel(yp)
#    if not parallax_ch: return
#
#    #print('Par', parallax.name)
#
#    loop = parallax.node_tree.nodes.get('_parallax_loop')
#    if loop:
#        tree = loop.node_tree
#        
#        loc = Vector((0,0))
#        check_set_node_loc(tree, TREE_START, loc)
#
#        loc.x += 200
#
#        for i in range(int(parallax_ch.parallax_num_of_layers)):
#            if check_set_node_loc(tree, '_iterate_' + str(i), loc):
#                loc.x += 200
#
#        check_set_node_loc(tree, TREE_END, loc)

def rearrange_parallax_process_internal_nodes(group_tree, node_name):
    yp = group_tree.yp

    #parallax = group_tree.nodes.get(PARALLAX)
    parallax = group_tree.nodes.get(node_name)

    #print('Metness', node_name)

    # Depth source nodes
    depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')

    start = depth_source_0.node_tree.nodes.get(TREE_START)
    loc = start.location.copy()
    loc.y -= 200

    for uv in yp.uvs:
        if check_set_node_loc(depth_source_0.node_tree, uv.parallax_delta_uv, loc):
            loc.y -= 200

        elif check_set_node_loc(depth_source_0.node_tree, uv.baked_parallax_delta_uv, loc):
            loc.y -= 200

        if check_set_node_loc(depth_source_0.node_tree, uv.parallax_current_uv, loc):
            loc.y -= 200

        elif check_set_node_loc(depth_source_0.node_tree, uv.baked_parallax_current_uv, loc):
            loc.y -= 200

    for tc in texcoord_lists:

        if check_set_node_loc(depth_source_0.node_tree, PARALLAX_DELTA_PREFIX + TEXCOORD_IO_PREFIX + tc, loc):
            loc.y -= 200

        if check_set_node_loc(depth_source_0.node_tree, PARALLAX_CURRENT_PREFIX + TEXCOORD_IO_PREFIX + tc, loc):
            loc.y -= 200

    # Parallax iteration nodes
    parallax_loop = parallax.node_tree.nodes.get('_parallax_loop')
    iterate = parallax_loop.node_tree.nodes.get('_iterate')

    depth_mix = iterate.node_tree.nodes.get('_depth_from_tex_mix')
    loc = depth_mix.location.copy()
    loc.y -= 200

    for uv in yp.uvs:
        if check_set_node_loc(iterate.node_tree, uv.parallax_current_uv_mix, loc):
            loc.y -= 200
        elif check_set_node_loc(iterate.node_tree, uv.baked_parallax_current_uv_mix, loc):
            loc.y -= 200

    for tc in texcoord_lists:

        if check_set_node_loc(iterate.node_tree, PARALLAX_CURRENT_MIX_PREFIX + TEXCOORD_IO_PREFIX + tc, loc):
            loc.y -= 200

    # Parallax mix nodes
    parallax_end = parallax.node_tree.nodes.get(TREE_END)
    loc = parallax_end.location.copy()
    loc.x -= 200

    for uv in yp.uvs:
        if check_set_node_loc(parallax.node_tree, uv.parallax_mix, loc):
            loc.y -= 200

        elif check_set_node_loc(parallax.node_tree, uv.baked_parallax_mix, loc):
            loc.y -= 200

    for tc in texcoord_lists:

        if check_set_node_loc(parallax.node_tree, PARALLAX_MIX_PREFIX + TEXCOORD_IO_PREFIX + tc, loc):
            loc.y -= 200

    #rearrange_parallax_layer_nodes(yp, parallax)
    rearrange_parallax_layer_nodes_(yp, parallax)

def rearrange_uv_nodes(group_tree, loc):
    yp = group_tree.yp

    if check_set_node_loc(group_tree, TEXCOORD, loc):
        loc.y -= 240

    if check_set_node_loc(group_tree, GEOMETRY, loc):
        loc.y -= 240

    if check_set_node_loc(group_tree, PARALLAX, loc):
        rearrange_parallax_process_internal_nodes(group_tree, PARALLAX)
        loc.y -= 240

    if check_set_node_loc(group_tree, BAKED_PARALLAX_FILTER, loc):
        loc.y -= 180

    if check_set_node_loc(group_tree, BAKED_PARALLAX, loc):
        rearrange_parallax_process_internal_nodes(group_tree, BAKED_PARALLAX)
        #rearrange_parallax_layer_nodes(yp, baked_parallax)
        loc.y -= 240

    for uv in yp.uvs:

        #if check_set_node_loc(group_tree, uv.parallax, loc):
        #    loc.y -= 240

        if check_set_node_loc(group_tree, uv.parallax_prep, loc):
            loc.y -= 280

        if check_set_node_loc(group_tree, uv.temp_tangent, loc):
            loc.y -= 180

        if check_set_node_loc(group_tree, uv.temp_bitangent, loc):
            loc.y -= 180

        if check_set_node_loc(group_tree, uv.tangent_flip, loc):
            loc.y -= 180

        if check_set_node_loc(group_tree, uv.bitangent_flip, loc):
            loc.y -= 120

        if check_set_node_loc(group_tree, uv.tangent, loc):
            loc.y -= 160

        if check_set_node_loc(group_tree, uv.bitangent, loc):
            loc.y -= 160

        if check_set_node_loc(group_tree, uv.tangent_process, loc):
            loc.y -= 160

        if check_set_node_loc(group_tree, uv.uv_map, loc):
            loc.y -= 120

    for tc in texcoord_lists:
        if check_set_node_loc(group_tree, tc + PARALLAX_PREP_SUFFIX, loc):
            loc.y -= 280

def rearrange_depth_layer_nodes(group_tree):
    yp = group_tree.yp

    parallax_ch = get_root_parallax_channel(yp)
    if not parallax_ch: return

    parallax = group_tree.nodes.get(PARALLAX)
    if not parallax: return

    depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
    tree = depth_source_0.node_tree

    start = tree.nodes.get(TREE_START)

    loc = start.location.copy()
    loc.x += 200

    # Layer nodes
    for i, t in enumerate(reversed(yp.layers)):

        parent_ids = get_list_of_parent_ids(t)

        loc.y = len(parent_ids) * -250

        if check_set_node_loc(tree, t.depth_group_node, loc):
            loc.x += 200

    if check_set_node_loc(tree, '_normalize', loc):
        loc.y -= 170

    if check_set_node_loc(tree, '_unpack', loc):
        loc.x += 200

    check_set_node_loc(tree, TREE_END, loc)

def rearrange_yp_nodes(group_tree):

    yp = group_tree.yp
    nodes = group_tree.nodes

    loc = Vector((-200, 0))

    # Rearrange depth layer nodes
    rearrange_depth_layer_nodes(group_tree)

    # Rearrange start nodes
    check_set_node_loc(group_tree, TREE_START, loc)

    loc.x += 200
    ori_x = loc.x

    num_channels = len(yp.channels)

    # Start nodes
    for i, channel in enumerate(yp.channels):

        # Start nodes
        if check_set_node_loc(group_tree, channel.start_linear, loc):
            if channel.type == 'RGB':
                loc.y -= 110
            elif channel.type == 'VALUE':
                loc.y -= 170

        if check_set_node_loc(group_tree, channel.start_normal_filter, loc):
            loc.y -= 120

        if check_set_node_loc(group_tree, channel.start_bump_process, loc):
            loc.y -= 250

        if i == num_channels-1:
            if check_set_node_loc(group_tree, ONE_VALUE, loc):
                loc.y -= 90
            if check_set_node_loc(group_tree, ZERO_VALUE, loc):
                loc.y -= 90
            check_set_node_loc(group_tree, GEOMETRY, loc)
            #loc.y -= 0

            # Rearrange uv nodes
            rearrange_uv_nodes(group_tree, loc)

    #groups = []
    #for i, t in enumerate(reversed(yp.layers)):
    #    if t.type == 'GROUP':
    #        pass

    loc.x += 200
    loc.y = 0.0

    # Layer nodes
    for i, t in enumerate(reversed(yp.layers)):

        parent_ids = get_list_of_parent_ids(t)

        #for pid in parent_ids:
        #    pass

        loc.y = len(parent_ids) * -250

        tnode = group_tree.nodes.get(t.group_node)
        check_set_node_width(tnode, 300)

        if check_set_node_loc(group_tree, t.group_node, loc):
        #if check_set_node_loc_x(group_tree, t.group_node, loc.x):
            loc.x += 350

    #stack = []
    #for i, t in enumerate(yp.layers):
    #    if stack and stack[-1] == t.parent_idx:
    #        loc.y += 300
    #        stack.pop()

    #    if t.type == 'GROUP':
    #        if check_set_node_loc_y(group_tree, t.group_node, loc.y):
    #            loc.y -= 300
    #            if t.parent_idx not in stack: stack.append(t.parent_idx)
    #    elif check_set_node_loc_y(group_tree, t.group_node, loc.y):
    #        pass

    #    #    if check_set_node_loc_y(group_tree, t.group_node, loc.y):
    #    #        print(t.name)
    #    #        loc.y -= 300
    #    #        if t.parent_idx not in stack: stack.append(t.parent_idx)
    #    #if stack and stack[-1] == t.parent_idx:
    #    #    loc.y += 300
    #    #    stack.pop()

    farthest_x = ori_x = loc.x

    # Modifiers
    for i, channel in enumerate(yp.channels):

        loc.x = ori_x

        loc, offset_y = arrange_modifier_nodes(
            group_tree, channel, loc, 
            is_value = channel.type == 'VALUE',
            return_y_offset = True
        )

        if loc.x > farthest_x: farthest_x = loc.x
        loc.y -= offset_y

    loc.x = farthest_x
    loc.y = 0.0

    # End nodes
    for i, channel in enumerate(yp.channels):

        #if not yp.use_baked and check_set_node_loc(group_tree, channel.end_normal_engine_filter, loc):
        #    loc.y -= 170

        if check_set_node_loc(group_tree, channel.end_linear, loc):
            if channel.type == 'RGB':
                loc.y -= 110
            elif channel.type == 'VALUE':
                loc.y -= 170
            elif channel.type == 'NORMAL':
                loc.y -= 300

        if check_set_node_loc(group_tree, channel.clamp, loc):
            loc.y -= 240

        if check_set_node_loc(group_tree, channel.end_max_height_tweak, loc):
            loc.y -= 220

        if check_set_node_loc(group_tree, channel.end_backface, loc):
            loc.y -= 180

    loc.x += 200
    loc.y = 0.0

    farthest_x = ori_x = loc.x

    for i, ch in enumerate(yp.channels):

        loc.x = ori_x

        if check_set_node_loc(group_tree, ch.baked, loc):
            loc.x += 270

        if yp.use_baked and check_set_node_loc(group_tree, channel.end_normal_engine_filter, loc):
            loc.x += 200

        if check_set_node_loc(group_tree, ch.baked_normal_prep, loc):
            loc.x += 200

        if check_set_node_loc(group_tree, ch.baked_normal, loc):
            loc.x += 200

        #if check_set_node_loc(group_tree, ch.baked_normal_flip, loc):
        #    loc.x += 200

        loc.y -= 270
        save_x = loc.x

        loc.x = ori_x

        if check_set_node_loc(group_tree, ch.baked_normal_overlay, loc):
            loc.y -= 270

        if check_set_node_loc(group_tree, ch.baked_disp, loc):
            loc.y -= 270

        if check_set_node_loc(group_tree, ch.end_max_height, loc):
            loc.y -= 110

        if check_set_node_loc(group_tree, ch.baked_vdisp, loc):
            loc.y -= 270

        if check_set_node_loc(group_tree, ch.baked_vcol, loc):
            loc.y -= 270

        loc.x = save_x

        if loc.x > farthest_x: farthest_x = loc.x

        #if i == num_channels-1:
        #    loc.x = ori_x

        #    check_set_node_loc(group_tree, BAKED_PARALLAX, loc)
        #    loc.y -= 190

        #    baked_parallax = group_tree.nodes.get(BAKED_PARALLAX)
        #    if baked_parallax:
        #        rearrange_parallax_layer_nodes(yp, baked_parallax)

            #check_set_node_loc(group_tree, BAKED_UV, loc)
            #loc.y -= 120

            #check_set_node_loc(group_tree, BAKED_TANGENT_FLIP, loc)
            #loc.y -= 170

            #check_set_node_loc(group_tree, BAKED_TANGENT, loc)
            #loc.y -= 170

            #check_set_node_loc(group_tree, BAKED_BITANGENT_FLIP, loc)
            #loc.y -= 120

            #check_set_node_loc(group_tree, BAKED_BITANGENT, loc)
            #loc.y -= 170

            #check_set_node_loc(group_tree, BAKED_NORMAL_FLIP, loc)
            #if check_set_node_loc(group_tree, BAKED_UV, loc):
                #loc.y -= 120
                #loc.x += 200

    for bt in yp.bake_targets:

        loc.x = ori_x

        if check_set_node_loc(group_tree, bt.image_node, loc):
            loc.x += 200

        loc.y -= 270

        if loc.x > farthest_x: farthest_x = loc.x

    loc.x = farthest_x
    loc.y = 0

    # End node
    check_set_node_loc(group_tree, TREE_END, loc)

    # Rearrange frames
    rearrange_yp_frame_nodes(yp)

