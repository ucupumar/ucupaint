import bpy, time
from mathutils import *
from .common import *

INFO_PREFIX = '__ytl_info_'

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
        }

value_mod_y_offsets = {
        'INVERT' : 270,
        'MULTIPLIER' :  270,
        }

def get_mod_y_offsets(mod, is_value=False):
    if is_value and mod.type in value_mod_y_offsets:
        return value_mod_y_offsets[mod.type]
    return mod_y_offsets[mod.type]

def check_set_node_loc(tree, node_name, loc, hide=False):
    node = tree.nodes.get(node_name)
    if node:
        if node.location != loc:
            node.location = loc
        if node.hide != hide:
            node.hide = hide
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

    #print('INFO: Unused frames cleaned at ', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def rearrange_tl_frame_nodes(tl):
    tree = tl.id_data
    nodes = tree.nodes

    # Channel loops
    for i, ch in enumerate(tl.channels):

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
        frame = get_frame(tree, '__modifiers__', str(i), ch.name + ' Final Modifiers')
        for mod in ch.modifiers:
            check_set_node_parent(tree, mod.frame, frame)

    clean_unused_frames(tree)

def rearrange_tex_frame_nodes(tex, tree=None):
    tl = tex.id_data.tl
    if not tree: tree = get_tree(tex)
    #nodes = tree.nodes

    # Texture channels
    for i, ch in enumerate(tex.channels):
        root_ch = tl.channels[i]

        # Modifiers
        if len(ch.modifiers) > 0:

            frame = get_frame(tree, '__modifier__', str(i), root_ch.name + ' Modifiers')

            #check_set_node_parent(tree, ch.start_rgb, frame)
            #check_set_node_parent(tree, ch.start_alpha, frame)
            #check_set_node_parent(tree, ch.end_rgb, frame)
            #check_set_node_parent(tree, ch.end_alpha, frame)

            # Modifiers
            if ch.mod_group != '':
                check_set_node_parent(tree, ch.mod_group, frame)
                check_set_node_parent(tree, ch.mod_n, frame)
                check_set_node_parent(tree, ch.mod_s, frame)
                check_set_node_parent(tree, ch.mod_e, frame)
                check_set_node_parent(tree, ch.mod_w, frame)
            else:
                for mod in ch.modifiers:
                    check_set_node_parent(tree, mod.frame, frame)

        #check_set_node_parent(tree, ch.linear, frame)
        #check_set_node_parent(tree, ch.source, frame)

        # Normal process

        if root_ch.type == 'NORMAL':

            frame = get_frame(tree, '__normal_process__', str(i), root_ch.name + ' Process')

            check_set_node_parent(tree, ch.bump_base, frame)
            check_set_node_parent(tree, ch.bump_base_n, frame)
            check_set_node_parent(tree, ch.bump_base_s, frame)
            check_set_node_parent(tree, ch.bump_base_e, frame)
            check_set_node_parent(tree, ch.bump_base_w, frame)
            check_set_node_parent(tree, ch.normal, frame)

        # Blend
        frame = get_frame(tree, '__blend__', str(i), root_ch.name + ' Blend')
        check_set_node_parent(tree, ch.intensity, frame)
        check_set_node_parent(tree, ch.blend, frame)
        check_set_node_parent(tree, ch.normal_flip, frame)
        #check_set_node_parent(tree, ch.intensity_multiplier, frame)

    # Masks
    for i, mask in enumerate(tex.masks):
        frame = get_frame(tree, '__mask__', str(i), mask.name)

        if mask.group_node != '':
            check_set_node_parent(tree, mask.group_node, frame)
        else: check_set_node_parent(tree, mask.source, frame)

        check_set_node_parent(tree, mask.uv_neighbor, frame)
        check_set_node_parent(tree, mask.uv_map, frame)
        check_set_node_parent(tree, mask.tangent, frame)
        check_set_node_parent(tree, mask.bitangent, frame)

        check_set_node_parent(tree, mask.source_n, frame)
        check_set_node_parent(tree, mask.source_s, frame)
        check_set_node_parent(tree, mask.source_e, frame)
        check_set_node_parent(tree, mask.source_w, frame)

        for c in mask.channels:
            check_set_node_parent(tree, c.multiply, frame)
            check_set_node_parent(tree, c.multiply_n, frame)
            check_set_node_parent(tree, c.multiply_s, frame)
            check_set_node_parent(tree, c.multiply_e, frame)
            check_set_node_parent(tree, c.multiply_w, frame)

    clean_unused_frames(tree)

def create_info_nodes(group_tree, tex=None):
    tl = group_tree.tl
    if tex:
        tree = get_tree(tex)
        nodes = tree.nodes
    else: nodes = group_tree.nodes

    # Delete previous info nodes
    for node in nodes:
        if node.name.startswith(INFO_PREFIX):
            nodes.remove(node)

    # Create info nodes
    infos = []

    info = nodes.new('NodeFrame')
    if tex:
        info.label = 'Part of yPaint addon version ' + tl.version
    else: info.label = 'Created using yPaint addon version ' + tl.version
    info.use_custom_color = True
    info.color = (1.0, 1.0, 1.0)
    if tex:
        info.width = 400.0
    else: info.width = 460.0
    info.height = 30.0
    infos.append(info)

    info = nodes.new('NodeFrame')
    info.label = 'Get this addon on patreon.com/ucupumar'
    info.use_custom_color = True
    info.color = (1.0, 1.0, 1.0)
    info.width = 420.0
    info.height = 30.0
    infos.append(info)

    info = nodes.new('NodeFrame')
    info.label = 'WARNING: Do NOT edit this group manually!'
    info.use_custom_color = True
    info.color = (1.0, 0.5, 0.5)
    info.width = 450.0
    info.height = 30.0
    infos.append(info)

    info = nodes.new('NodeFrame')
    info.label = 'Please use this panel: Node Editor > Tools > Texture Layers'
    info.use_custom_color = True
    info.color = (1.0, 0.5, 0.5)
    info.width = 580.0
    info.height = 30.0
    infos.append(info)

    loc = Vector((0, 70))

    for info in reversed(infos):
        info.name = INFO_PREFIX + info.name

        loc.y += 40
        info.location = loc

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

    return loc

def arrange_modifier_nodes(tree, parent, loc, is_value=False, return_y_offset=False):

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

    # Modifier loops
    for m in reversed(parent.modifiers):

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

def rearrange_source_tree_nodes(tex):

    source_tree = get_source_tree(tex)

    loc = Vector((0, 0))

    if check_set_node_loc(source_tree, SOURCE_TREE_START, loc):
        loc.x += 180

    loc.y -= 300
    check_set_node_loc(source_tree, SOURCE_SOLID_VALUE, loc)
    loc.y += 300

    if check_set_node_loc(source_tree, tex.mapping, loc):
        loc.x += 380

    if check_set_node_loc(source_tree, tex.source, loc):
        loc.x += 200

    if tex.type in {'IMAGE', 'VCOL'}:
        arrange_modifier_nodes(source_tree, tex, loc)
    else:
        if check_set_node_loc(source_tree, tex.mod_group, loc, True):
            mod_group = source_tree.nodes.get(tex.mod_group)
            arrange_modifier_nodes(mod_group.node_tree, tex, loc=Vector((0,0)))
            loc.y -= 40
        if check_set_node_loc(source_tree, tex.mod_group_1, loc, True):
            loc.y += 40
            loc.x += 150

    check_set_node_loc(source_tree, SOURCE_TREE_END, loc)

def rearrange_mask_tree_nodes(mask):
    tree = get_mask_tree(mask)
    loc = Vector((0, 0))

    if check_set_node_loc(tree, MASK_TREE_START, loc):
        loc.x += 180

    if check_set_node_loc(tree, mask.mapping, loc):
        loc.x += 380

    if check_set_node_loc(tree, mask.source, loc):
        loc.x += 180

    arrange_mask_modifier_nodes(tree, mask, loc)

    if check_set_node_loc(tree, MASK_TREE_END, loc):
        loc.x += 180

def rearrange_transition_bump_nodes(tree, ch, loc):
    # Bump

    ori_x = loc.x

    if check_set_node_loc(tree, ch.tb_bump, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.tb_inverse, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.tb_intensity_multiplier, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.tb_blend, loc):
        loc.x += 200.0

    save_x = loc.x
    loc.x = ori_x

    loc.y -= 300.0
    if not check_set_node_loc(tree, ch.tb_crease, loc):
        loc.y += 300.0

    loc.x = save_x

def rearrange_normal_process_nodes(tree, ch, loc):

    bookmark_y = loc.y

    if check_set_node_loc(tree, ch.bump_base, loc):
        loc.x += 200

    loc.y -= 40
    if check_set_node_loc(tree, ch.bump_base_n, loc, hide=True):
        loc.y -= 40
    else: loc.y += 40

    if check_set_node_loc(tree, ch.bump_base_s, loc, hide=True):
        loc.y -= 40

    if check_set_node_loc(tree, ch.bump_base_e, loc, hide=True):
        loc.y -= 40

    if check_set_node_loc(tree, ch.bump_base_w, loc, hide=True):
        loc.y = bookmark_y
        loc.x += 120

    if check_set_node_loc(tree, ch.normal, loc):
        loc.x += 250

def rearrange_tex_nodes(tex, tree=None):
    tl = tex.id_data.tl

    if tl.halt_reconnect: return

    if not tree: tree = get_tree(tex)
    nodes = tree.nodes

    #print('Rearrange texture ' + tex.name)

    start = nodes.get(tex.start)
    end = nodes.get(tex.end)

    # Get transition bump channel
    flip_bump = False
    chain = -1
    bump_ch = get_transition_bump_channel(tex)
    if bump_ch:
        flip_bump = bump_ch.transition_bump_flip or tex.type == 'BACKGROUND'
        #flip_bump = bump_ch.transition_bump_flip
        chain = min(len(tex.masks), bump_ch.transition_bump_chain)

    #start_x = 350
    #loc = Vector((350, 0))

    # Back to source nodes
    loc = Vector((0, 0))

    if tex.source_group != '' and check_set_node_loc(tree, tex.source_group, loc, hide=True):
        rearrange_source_tree_nodes(tex)
        loc.y -= 40

    elif check_set_node_loc(tree, tex.source, loc, hide=False):
        if tex.type == 'BRICK':
            loc.y -= 400
        elif tex.type == 'CHECKER':
            loc.y -= 170
        elif tex.type == 'GRADIENT':
            loc.y -= 140
        elif tex.type == 'MAGIC':
            loc.y -= 180
        elif tex.type == 'MUSGRAVE':
            loc.y -= 270
        elif tex.type == 'NOISE':
            loc.y -= 170
        elif tex.type == 'VORONOI':
            loc.y -= 170
        elif tex.type == 'VORONOI':
            loc.y -= 260
        else:
            loc.y -= 260

    if check_set_node_loc(tree, tex.source_n, loc, hide=True):
        loc.y -= 40

    if check_set_node_loc(tree, tex.source_s, loc, hide=True):
        loc.y -= 40

    if check_set_node_loc(tree, tex.source_e, loc, hide=True):
        loc.y -= 40

    if check_set_node_loc(tree, tex.source_w, loc, hide=True):
        loc.y -= 40

    if tex.source_group == '' and check_set_node_loc(tree, tex.mapping, loc):
        loc.y -= 290

    if check_set_node_loc(tree, tex.uv_neighbor, loc):
        loc.y -= 230

    if check_set_node_loc(tree, tex.uv_map, loc):
        loc.y -= 140

    if check_set_node_loc(tree, tex.solid_value, loc):
        loc.y -= 90

    if check_set_node_loc(tree, tex.texcoord, loc):
        loc.y -= 240

    if check_set_node_loc(tree, tex.tangent, loc):
        loc.y -= 160

    if check_set_node_loc(tree, tex.bitangent, loc):
        loc.y -= 160

    if check_set_node_loc(tree, tex.geometry, loc):
        loc.y -= 210

    loc = Vector((-600, 0))

    # Channel Caches
    for ch in tex.channels:

        if check_set_node_loc(tree, ch.cache_ramp, loc, hide=False):
            loc.y -= 270

    loc = Vector((-300, 0))

    # Layer Caches
    if check_set_node_loc(tree, tex.cache_color, loc, hide=False):
        loc.y -= 200

    if check_set_node_loc(tree, tex.cache_brick, loc, hide=False):
        loc.y -= 400

    if check_set_node_loc(tree, tex.cache_checker, loc, hide=False):
        loc.y -= 170

    if check_set_node_loc(tree, tex.cache_gradient, loc, hide=False):
        loc.y -= 140

    if check_set_node_loc(tree, tex.cache_magic, loc, hide=False):
        loc.y -= 180

    if check_set_node_loc(tree, tex.cache_musgrave, loc, hide=False):
        loc.y -= 270

    if check_set_node_loc(tree, tex.cache_noise, loc, hide=False):
        loc.y -= 170

    if check_set_node_loc(tree, tex.cache_voronoi, loc, hide=False):
        loc.y -= 170

    if check_set_node_loc(tree, tex.cache_wave, loc, hide=False):
        loc.y -= 260

    loc = Vector((380, 0))

    # Texture modifiers
    if tex.source_group == '':
        if tex.mod_group != '':
            mod_group = nodes.get(tex.mod_group)
            arrange_modifier_nodes(mod_group.node_tree, tex, loc.copy())
            check_set_node_loc(tree, tex.mod_group, loc, hide=True)
            loc.y -= 40
            check_set_node_loc(tree, tex.mod_group_1, loc, hide=True)
            loc.y += 40
            loc.x += 200
        else:
            loc = arrange_modifier_nodes(tree, tex, loc)

    start_x = loc.x
    farthest_x = 0
    bookmarks_ys = []

    for i, ch in enumerate(tex.channels):

        root_ch = tl.channels[i]

        if root_ch.type == 'NORMAL':
            chain = min(len(tex.masks), ch.transition_bump_chain)
        elif bump_ch:
            chain = min(len(tex.masks), bump_ch.transition_bump_chain)
        else:
            chain = -1

        loc.x = start_x
        bookmark_y = loc.y
        bookmarks_ys.append(bookmark_y)
        offset_y = NO_MODIFIER_Y_OFFSET
        #offset_y = 0

        #if check_set_node_loc(tree, ch.source, loc):
        #    loc.x += 200

        if check_set_node_loc(tree, ch.linear, loc):
            loc.x += 200

        # Modifier loop
        if ch.mod_group != '':
            mod_group = nodes.get(ch.mod_group)
            arrange_modifier_nodes(mod_group.node_tree, ch, Vector((0,0)))
            check_set_node_loc(tree, ch.mod_group, loc, hide=True)
            loc.y -= 40
        else:
            loc, mod_offset_y = arrange_modifier_nodes(tree, ch, loc, 
                    is_value = root_ch.type == 'VALUE', return_y_offset = True)

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

        if bump_ch or chain == 0:
            rearrange_normal_process_nodes(tree, ch, loc)

        if loc.x > farthest_x: farthest_x = loc.x

        if root_ch.type == 'NORMAL': #and ch.normal_map_type == 'FINE_BUMP_MAP' and offset_y < FINE_BUMP_Y_OFFSET:
            if offset_y < FINE_BUMP_Y_OFFSET:
                offset_y = FINE_BUMP_Y_OFFSET

        loc.y -= offset_y

        # If next channel had modifier
        if i+1 < len(tex.channels):
            next_ch = tex.channels[i+1]
            if len(next_ch.modifiers) > 0 and next_ch.mod_group == '':
                loc.y -= 35

    if bookmarks_ys:
        mid_y = (bookmarks_ys[-1]) / 2
    else: mid_y = 0

    y_step = 200
    y_mid = -(len(tex.channels) * y_step / 2)

    if bump_ch and chain == 0:

        loc.x = farthest_x
        loc.y = 0
        bookmark_x = loc.x

        for i, ch in enumerate(tex.channels):

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
    for i, mask in enumerate(tex.masks):

        loc.y = 0
        loc.x = farthest_x

        if mask.group_node != '' and check_set_node_loc(tree, mask.group_node, loc, True):
            rearrange_mask_tree_nodes(mask)
            loc.y -= 40

        elif check_set_node_loc(tree, mask.source, loc):
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

        if check_set_node_loc(tree, mask.mapping, loc):
            loc.y -= 290

        if check_set_node_loc(tree, mask.uv_map, loc):
            loc.y -= 130

        if check_set_node_loc(tree, mask.tangent, loc):
            loc.y -= 170

        if check_set_node_loc(tree, mask.bitangent, loc):
            loc.y -= 180

        loc.y = 0

        if mask.group_node == '' and len(mask.modifiers) > 0:
            loc.x += 180
            arrange_mask_modifier_nodes(tree, mask, loc)
            loc.x += 20
        else:
            loc.x += 370

        bookmark_x = loc.x

        # Mask channels
        for j, c in enumerate(mask.channels):

            ch = tex.channels[j]
            root_ch = tl.channels[j]

            if root_ch.type == 'NORMAL':
                chain = min(len(tex.masks), ch.transition_bump_chain)
            elif bump_ch:
                chain = min(len(tex.masks), bump_ch.transition_bump_chain)
            else:
                chain = -1

            loc.x = bookmark_x
            bookmark_y = loc.y

            mul_n = tree.nodes.get(c.multiply_n)
            if not mul_n:

                if check_set_node_loc(tree, c.multiply, loc):
                    loc.y -= 200.0
            else:

                if check_set_node_loc(tree, c.multiply, loc, True):
                    loc.y -= 40

                if check_set_node_loc(tree, c.multiply_n, loc, True):
                    loc.y -= 40

                if check_set_node_loc(tree, c.multiply_s, loc, True):
                    loc.y -= 40

                if check_set_node_loc(tree, c.multiply_e, loc, True):
                    loc.y -= 40

                if check_set_node_loc(tree, c.multiply_w, loc, True):
                    loc.y -= 40

            loc.x += 230
            bookmark_y1 = loc.y
            loc.y = bookmark_y

            # Transition effects
            if i == chain-1:

                ch = tex.channels[j]

                if check_set_node_loc(tree, ch.intensity_multiplier, loc, False):
                    loc.y -= 200

                if flip_bump and check_set_node_loc(tree, ch.tao, loc, False):
                    loc.y -= 230

                #if not flip_bump and ch.enable and ch.enable_transition_ramp:
                if ch.enable_transition_ramp and (not ch.transition_ramp_intensity_unlink 
                        or flip_bump or ch.transition_ramp_blend_type != 'MIX'):
                    if check_set_node_loc(tree, ch.tr_ramp, loc):
                        loc.y -= 230

                if bump_ch == ch:
                    rearrange_transition_bump_nodes(tree, ch, loc)
                    loc.y -= 300

                if not bump_ch:
                    rearrange_normal_process_nodes(tree, ch, loc)
                    loc.y -= 300

            else:
                loc.y = bookmark_y1

            if loc.x > farthest_x: farthest_x = loc.x

    loc.x = farthest_x
    loc.y = 0
    bookmark_x = loc.x

    for i, ch in enumerate(tex.channels):

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
    check_set_node_loc(tree, tex.start, loc)

    loc.x += 250
    loc.y = 0

    bookmark_x = loc.x

    # Channel blends
    for i, ch in enumerate(tex.channels):

        loc.x = bookmark_x
        #loc.y = bookmarks_ys[i]

        y_offset = 240

        #if ch != bump_ch or (ch == bump_ch and chain == len(tex.masks)):
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

        if check_set_node_loc(tree, ch.intensity, loc):
            loc.x += 200

        if (ch.enable_transition_ramp and not flip_bump and ch.transition_ramp_intensity_unlink 
                and ch.transition_ramp_blend_type == 'MIX'):
            if check_set_node_loc(tree, ch.tr_ramp, loc):
                loc.x += 200
                #y_offset += 60

        save_y = loc.y
        save_x = loc.x

        loc.y -= 170
        loc.x = bookmark_x

        if check_set_node_loc(tree, ch.normal_flip, loc):
            loc.y -= 130
            y_offset += 130

        if check_set_node_loc(tree, ch.tb_crease_intensity, loc):
            loc.x += 200

        if check_set_node_loc(tree, ch.tb_crease_mix, loc):
            loc.x += 200
            loc.y -= 200
            y_offset += 200

        loc.y = save_y
        if loc.x < save_x:
            loc.x = save_x

        if check_set_node_loc(tree, ch.blend, loc):
            loc.x += 250

        if loc.x > farthest_x: farthest_x = loc.x

        #loc.y -= y_step
        #loc.y -= 240
        loc.y -= y_offset

    loc.x = farthest_x
    #loc.y = mid_y
    #loc.y = y_mid
    loc.y = 0
    check_set_node_loc(tree, tex.end, loc)

    rearrange_tex_frame_nodes(tex, tree)

def rearrange_tl_nodes(group_tree):

    tl = group_tree.tl
    nodes = group_tree.nodes

    dist_y = 185
    dist_x = 200
    loc = Vector((0, 0))

    # Rearrange start nodes
    check_set_node_loc(group_tree, tl.start, loc)

    loc.x += 200
    ori_x = loc.x

    num_channels = len(tl.channels)

    # Start nodes
    for i, channel in enumerate(tl.channels):

        # Start nodes
        if check_set_node_loc(group_tree, channel.start_linear, loc):
            if channel.type == 'RGB':
                loc.y -= 110
            elif channel.type == 'VALUE':
                loc.y -= 170

        if check_set_node_loc(group_tree, channel.start_normal_filter, loc):
            loc.y -= 120

        if i == num_channels-1:
            check_set_node_loc(group_tree, tl.solid_value, loc)
            loc.x += 200

    #groups = []
    #for i, t in enumerate(reversed(tl.textures)):
    #    if t.type == 'GROUP':
    #        pass

    loc.y = 0.0

    # Texture nodes
    for i, t in enumerate(reversed(tl.textures)):

        parent_ids = get_list_of_parent_ids(t)

        #for pid in parent_ids:
        #    pass

        loc.y = len(parent_ids) * -250

        if check_set_node_loc(group_tree, t.group_node, loc):
        #if check_set_node_loc_x(group_tree, t.group_node, loc.x):
            loc.x += 200

    #stack = []
    #for i, t in enumerate(tl.textures):
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
    for i, channel in enumerate(tl.channels):

        loc.x = ori_x

        loc, offset_y = arrange_modifier_nodes(group_tree, channel, loc, 
                is_value = channel.type == 'VALUE', return_y_offset = True)

        if loc.x > farthest_x: farthest_x = loc.x
        loc.y -= offset_y

    loc.x = farthest_x
    loc.y = 0.0

    # End nodes
    for i, channel in enumerate(tl.channels):
        if check_set_node_loc(group_tree, channel.end_linear, loc):
            if channel.type == 'RGB':
                loc.y -= 110
            elif channel.type == 'VALUE':
                loc.y -= 170

    loc.x += 200
    loc.y = 0.0

    # End node
    check_set_node_loc(group_tree, tl.end, loc)

    # Rearrange frames
    rearrange_tl_frame_nodes(tl)

