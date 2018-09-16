import bpy
from mathutils import *
from .common import *

INFO_PREFIX = '__ytl_info_'

NO_MODIFIER_Y_OFFSET = 235
FINE_BUMP_Y_OFFSET = 300

default_y_offsets = {
        'RGB' : 165,
        'VALUE' : 220,
        'NORMAL' : 155,
        }

mod_y_offsets = {
        'INVERT' : 330,
        'RGB_TO_INTENSITY' : 270,
        'INTENSITY_TO_RGB' : 270,
        'OVERRIDE_COLOR' : 270,
        'COLOR_RAMP' : 315,
        'RGB_CURVE' : 390,
        'HUE_SATURATION' : 265,
        'BRIGHT_CONTRAST' : 220,
        'MULTIPLIER' :  350,
        }

value_mod_y_offsets = {
        'INVERT' : 250,
        'MULTIPLIER' :  250,
        }

def get_mod_y_offsets(mod, is_value=False):
    if is_value and mod.type in value_mod_y_offsets:
        return value_mod_y_offsets[mod.type]
    return mod_y_offsets[mod.type]

def check_set_node_loc(tree, node_name, loc):
    node = tree.nodes.get(node_name)
    if node:
        if node.location != loc:
            node.location = loc
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

def check_set_node_label(node, label):
    if node and node.label != label:
        node.label = label

def refresh_tl_channel_frame(ch, nodes):

    start_frame = nodes.get(ch.start_frame)
    if not start_frame:
        start_frame = nodes.new('NodeFrame')
        ch.start_frame = start_frame.name

    check_set_node_label(start_frame, ch.name + ' Start')

    end_frame = nodes.get(ch.end_frame)
    if not end_frame:
        end_frame = nodes.new('NodeFrame')
        ch.end_frame = end_frame.name

    check_set_node_label(end_frame, ch.name + ' End')

    return start_frame, end_frame

def refresh_tex_channel_frame(root_ch, ch, nodes):

    pipeline_frame = nodes.get(ch.pipeline_frame)
    if not pipeline_frame:
        pipeline_frame = nodes.new('NodeFrame')
        ch.pipeline_frame = pipeline_frame.name

    check_set_node_label(pipeline_frame, root_ch.name + ' Pipeline')

    blend = nodes.get(ch.blend)
    if blend:
        check_set_node_label(blend, root_ch.name + ' Blend')

    return pipeline_frame

def rearrange_tl_frame_nodes(group_tree):
    tl = group_tree.tl
    nodes = group_tree.nodes

    # Channel loops
    for ch in tl.channels:

        start_frame, end_frame = refresh_tl_channel_frame(ch, nodes)

        # Start Frame
        check_set_node_parent(group_tree, ch.start_entry, start_frame)
        check_set_node_parent(group_tree, ch.start_linear, start_frame)
        check_set_node_parent(group_tree, ch.start_alpha_entry, start_frame)
        check_set_node_parent(group_tree, ch.start_normal_filter, start_frame)

        # End Frame
        check_set_node_parent(group_tree, ch.end_entry, end_frame)
        check_set_node_parent(group_tree, ch.end_alpha_entry, end_frame)
        check_set_node_parent(group_tree, ch.start_rgb, end_frame)
        check_set_node_parent(group_tree, ch.start_alpha, end_frame)
        check_set_node_parent(group_tree, ch.end_rgb, end_frame)
        check_set_node_parent(group_tree, ch.end_alpha, end_frame)
        check_set_node_parent(group_tree, ch.end_linear, end_frame)

        # Modifiers
        for mod in ch.modifiers:
            frame = nodes.get(mod.frame)
            check_set_node_parent(group_tree, mod.frame, end_frame)

def rearrange_tex_frame_nodes(tex):
    tl = get_active_texture_layers_node().node_tree.tl
    tree = get_tree(tex)
    nodes = tree.nodes

    # Texture channels
    for i, ch in enumerate(tex.channels):
        root_ch = tl.channels[i]

        pipeline_frame = refresh_tex_channel_frame(root_ch, ch, nodes)
        
        check_set_node_parent(tree, ch.linear, pipeline_frame)
        check_set_node_parent(tree, ch.source, pipeline_frame)

        check_set_node_parent(tree, ch.start_rgb, pipeline_frame)
        check_set_node_parent(tree, ch.start_alpha, pipeline_frame)
        check_set_node_parent(tree, ch.end_rgb, pipeline_frame)
        check_set_node_parent(tree, ch.end_alpha, pipeline_frame)

        check_set_node_parent(tree, ch.bump_base, pipeline_frame)
        check_set_node_parent(tree, ch.bump, pipeline_frame)
        check_set_node_parent(tree, ch.normal, pipeline_frame)
        #check_set_node_parent(tree, ch.normal_flip, pipeline_frame)

        check_set_node_parent(tree, ch.neighbor_uv, pipeline_frame)
        check_set_node_parent(tree, ch.fine_bump, pipeline_frame)
        check_set_node_parent(tree, ch.source_n, pipeline_frame)
        check_set_node_parent(tree, ch.source_s, pipeline_frame)
        check_set_node_parent(tree, ch.source_e, pipeline_frame)
        check_set_node_parent(tree, ch.source_w, pipeline_frame)
        check_set_node_parent(tree, ch.mod_n, pipeline_frame)
        check_set_node_parent(tree, ch.mod_s, pipeline_frame)
        check_set_node_parent(tree, ch.mod_e, pipeline_frame)
        check_set_node_parent(tree, ch.mod_w, pipeline_frame)
        check_set_node_parent(tree, ch.bump_base_n, pipeline_frame)
        check_set_node_parent(tree, ch.bump_base_s, pipeline_frame)
        check_set_node_parent(tree, ch.bump_base_e, pipeline_frame)
        check_set_node_parent(tree, ch.bump_base_w, pipeline_frame)

        #check_set_node_parent(tree, ch.intensity_multiplier, pipeline_frame)
        #check_set_node_parent(tree, ch.intensity, pipeline_frame)

        # Modifiers
        if ch.mod_group != '':
            mod_group = nodes.get(ch.mod_group)
            check_set_node_parent(tree, ch.mod_group, pipeline_frame)
        else:
            for mod in ch.modifiers:
                frame = nodes.get(mod.frame)
                check_set_node_parent(tree, mod.frame, pipeline_frame)

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
        info.label = 'Part of yTexLayers addon version ' + tl.version
    else: info.label = 'Created using yTexLayers addon version ' + tl.version
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

def arrange_modifier_nodes(tree, parent, loc, is_value=False, return_y_offset=False):

    ori_y = loc.y

    offset_y = 0

    if check_set_node_loc(tree, TREE_START, loc):
        loc.x += 200

    # Modifier loops
    for m in reversed(parent.modifiers):

        loc.y -= 35
        check_set_node_loc(tree, m.start_rgb, loc)

        loc.y -= 35
        check_set_node_loc(tree, m.start_alpha, loc)

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

        loc.y -= 35
        check_set_node_loc(tree, m.end_rgb, loc)
        loc.y -= 35
        check_set_node_loc(tree, m.end_alpha, loc)

        loc.y = ori_y
        loc.x += 100

    if check_set_node_loc(tree, TREE_END, loc):
        loc.x += 200

    if return_y_offset:
        return loc, offset_y
    return loc

def rearrange_source_tree_nodes(tex):

    source_tree = get_source_tree(tex)

    loc = Vector((0, 0))

    if check_set_node_loc(source_tree, TREE_START, loc):
        loc.x += 180

    if check_set_node_loc(source_tree, tex.source, loc):
        loc.x += 180

    check_set_node_loc(source_tree, TREE_END, loc)

def rearrange_mask_tree_nodes(mask):
    tree = get_mask_tree(mask)
    loc = Vector((0, 0))

    if check_set_node_loc(tree, MASK_TREE_START, loc):
        loc.x += 180

    if check_set_node_loc(tree, mask.source, loc):
        loc.x += 180

    if check_set_node_loc(tree, mask.hardness, loc):
        loc.x += 180

    if check_set_node_loc(tree, MASK_TREE_END, loc):
        loc.x += 180

def rearrange_mask_bump_nodes(tree, ch, loc):
    # Bump

    if check_set_node_loc(tree, ch.mb_fine_bump, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.mb_bump, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.mb_inverse, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.mb_intensity_multiplier, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.mb_blend, loc):
        loc.x += 170.0

def rearrange_mask_ramp_nodes(tree, ch, loc):
    # Ramp

    if check_set_node_loc(tree, ch.mr_inverse, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.mr_ramp, loc):
        loc.x += 270.0

    if check_set_node_loc(tree, ch.mr_linear, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.mr_intensity_multiplier, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.mr_alpha, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.mr_alpha1, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.mr_intensity, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.mr_blend, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.mr_flip_hack, loc):
        loc.x += 170.0

    if check_set_node_loc(tree, ch.mr_flip_blend, loc):
        loc.x += 170.0

def rearrange_tex_nodes(tex):
    tl = tex.id_data.tl
    tree = get_tree(tex)
    nodes = tree.nodes

    start = nodes.get(tex.start)
    end = nodes.get(tex.end)

    # Get bump channel
    bump_ch = None
    flip_bump = False
    #if len(tex.masks) > 0:
    for i, c in enumerate(tex.channels):
        if tl.channels[i].type == 'NORMAL' and c.enable_mask_bump and c.enable:
            bump_ch = c
            if bump_ch.mask_bump_flip:
                flip_bump = True
            break

    #start_x = 350
    loc = Vector((350, 0))

    # Texture modifiers
    loc = arrange_modifier_nodes(tree, tex, loc)

    start_x = loc.x
    farthest_x = 0
    bookmarks_ys = []

    offset_y = NO_MODIFIER_Y_OFFSET

    for i, ch in enumerate(tex.channels):

        root_ch = tl.channels[i]

        loc.x = start_x
        bookmark_y = loc.y
        bookmarks_ys.append(bookmark_y)

        #if check_set_node_loc(tree, ch.source, loc):
        #    loc.x += 200.0

        if check_set_node_loc(tree, ch.linear, loc):
            loc.x += 200.0

        loc.y -= 35
        check_set_node_loc(tree, ch.start_rgb, loc)

        loc.y -= 35
        check_set_node_loc(tree, ch.start_alpha, loc)

        loc.x += 50
        loc.y = bookmark_y

        # Modifier loop
        if ch.mod_group != '':
            mod_group = nodes.get(ch.mod_group)
            arrange_modifier_nodes(mod_group.node_tree, ch, Vector((0,0)))
            check_set_node_loc(tree, ch.mod_group, loc)
            loc.x += 200
        else:
            loc, mod_offset_y = arrange_modifier_nodes(tree, ch, loc, 
                    is_value = root_ch.type == 'VALUE', return_y_offset = True)

            if offset_y < mod_offset_y:
                offset_y = mod_offset_y

        loc.y -= 35
        check_set_node_loc(tree, ch.end_rgb, loc)

        loc.y -= 35
        check_set_node_loc(tree, ch.end_alpha, loc)

        loc.x += 50
        loc.y = bookmark_y

        if check_set_node_loc(tree, ch.bump_base, loc):
            loc.x += 200.0

        if check_set_node_loc(tree, ch.bump, loc):
            loc.x += 200.0

        if check_set_node_loc(tree, ch.normal, loc):
            loc.x += 200.0

        if check_set_node_loc(tree, ch.neighbor_uv, loc):
            loc.x += 200.0

        if check_set_node_loc(tree, ch.source_n, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.source_s, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.source_e, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.source_w, loc):
            loc.y = bookmark_y
            loc.x += 120.0

        if check_set_node_loc(tree, ch.mod_n, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.mod_s, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.mod_e, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.mod_w, loc):
            loc.y = bookmark_y
            loc.x += 120.0

        if check_set_node_loc(tree, ch.bump_base_n, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.bump_base_s, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.bump_base_e, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.bump_base_w, loc):
            loc.y = bookmark_y
            loc.x += 200.0

        if check_set_node_loc(tree, ch.fine_bump, loc):
            loc.x += 200.0

        if loc.x > farthest_x: farthest_x = loc.x

        if root_ch.type == 'NORMAL' and ch.normal_map_type == 'FINE_BUMP_MAP' and offset_y < FINE_BUMP_Y_OFFSET:
            offset_y = FINE_BUMP_Y_OFFSET

        loc.y -= offset_y

        # If next channel had modifier
        if i+1 < len(tex.channels):
            next_ch = tex.channels[i+1]
            if len(next_ch.modifiers) > 0:
                loc.y -= 35

    if bookmarks_ys:
        mid_y = (bookmarks_ys[-1]) / 2
    else: mid_y = 0

    loc.x = farthest_x
    loc.y = 0
    bookmark_x = loc.x

    # Source mask bump
    for i, ch in enumerate(tex.channels):

        loc.x = bookmark_x
        loc.y = bookmarks_ys[i]

        if check_set_node_loc(tree, ch.mb_neighbor_uv, loc):
            loc.x += 200.0

        if check_set_node_loc(tree, ch.mb_source_n, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.mb_source_s, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.mb_source_e, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.mb_source_w, loc):
            loc.y = bookmarks_ys[i]
            loc.x += 120.0

        if check_set_node_loc(tree, ch.mb_mod_n, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.mb_mod_s, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.mb_mod_e, loc):
            loc.y -= 40.0

        if check_set_node_loc(tree, ch.mb_mod_w, loc):
            #loc.y = bookmarks_ys[i]
            loc.x += 150.0

        if loc.x > farthest_x: farthest_x = loc.x

    # Masks
    for i, mask in enumerate(tex.masks):

        loc.y = mid_y
        loc.x = farthest_x

        #if check_set_node_loc(tree, mask.source, loc):
        if mask.group_node != '' and check_set_node_loc(tree, mask.group_node, loc):
            rearrange_mask_tree_nodes(mask)
            #loc.x += 200
            loc.y -= 140
        elif check_set_node_loc(tree, mask.source, loc):
            loc.y -= 270

        if check_set_node_loc(tree, mask.uv_map, loc):
            loc.y -= 130

        if check_set_node_loc(tree, mask.tangent, loc):
            #loc.x += 200
            loc.y -= 170

        if check_set_node_loc(tree, mask.bitangent, loc):
            #loc.x += 200
            loc.y -= 180

        loc.x += 280
        loc.y = mid_y

        if check_set_node_loc(tree, mask.hardness, loc):
            loc.x += 200

        if mask.final != '':
            loc.y -= 35
            check_set_node_loc(tree, mask.final, loc)
            loc.x += 50

        #loc.y -= 235

        bookmark_x = loc.x

        # Mask channels
        for j, c in enumerate(mask.channels):

            loc.x = bookmark_x
            loc.y = bookmarks_ys[j]

            if check_set_node_loc(tree, c.multiply, loc):
                loc.x += 200.0

            # Bump stuff
            if check_set_node_loc(tree, c.neighbor_uv, loc):
                loc.x += 180.0

            save_x = loc.x

            if check_set_node_loc(tree, c.source_n, loc):
                loc.x += 120.0

            if check_set_node_loc(tree, c.multiply_n, loc):
                loc.y -= 40.0
                loc.x = save_x

            if check_set_node_loc(tree, c.source_s, loc):
                loc.x += 120.0

            if check_set_node_loc(tree, c.multiply_s, loc):
                loc.y -= 40.0
                loc.x = save_x

            if check_set_node_loc(tree, c.source_e, loc):
                loc.x += 120.0

            if check_set_node_loc(tree, c.multiply_e, loc):
                loc.y -= 40.0
                loc.x = save_x

            if check_set_node_loc(tree, c.source_w, loc):
                loc.x += 120.0

            if check_set_node_loc(tree, c.multiply_w, loc):
                loc.y = bookmarks_ys[j]
                loc.x += 140.0

            if loc.x > farthest_x: farthest_x = loc.x + 50

    loc.x = farthest_x
    loc.y = 0
    bookmark_x = loc.x

    for i, ch in enumerate(tex.channels):

        loc.x = bookmark_x
        loc.y = bookmarks_ys[i]

        if bump_ch and not flip_bump and bump_ch.mask_bump_mask_only:
            rearrange_mask_ramp_nodes(tree, ch, loc)

        if ch.mask_bump_mask_only:
            rearrange_mask_bump_nodes(tree, ch, loc)

        if loc.x > farthest_x: farthest_x = loc.x

    loc.x = farthest_x
    loc.y = 0
    bookmark_x = loc.x

    for i, ch in enumerate(tex.channels):

        loc.x = bookmark_x
        loc.y = bookmarks_ys[i]

        if check_set_node_loc(tree, ch.mask_intensity_multiplier, loc):
            loc.x += 200.0

        if loc.x > farthest_x: farthest_x = loc.x

    loc.x = farthest_x
    loc.y = 0
    bookmark_x = loc.x

    for i, ch in enumerate(tex.channels):

        loc.x = bookmark_x
        loc.y = bookmarks_ys[i]

        if check_set_node_loc(tree, ch.mask_total, loc):
            loc.x += 200.0

        if loc.x > farthest_x: farthest_x = loc.x

    loc.x = farthest_x
    loc.y = 0
    bookmark_x = loc.x

    for i, ch in enumerate(tex.channels):

        loc.x = bookmark_x
        loc.y = bookmarks_ys[i]

        #if bump_ch and not flip_bump and not bump_ch.mask_bump_mask_only:
        if not flip_bump and (not bump_ch or (bump_ch and not bump_ch.mask_bump_mask_only)):
            rearrange_mask_ramp_nodes(tree, ch, loc)

        if not ch.mask_bump_mask_only:
            rearrange_mask_bump_nodes(tree, ch, loc)

        if loc.x > farthest_x: farthest_x = loc.x

    #loc.x += 200
    loc.x = farthest_x
    loc.y = mid_y

    # Start node
    check_set_node_loc(tree, tex.start, loc)

    loc.x += 250
    loc.y = 0

    # If flip bump
    if flip_bump and bump_ch and bump_ch.mask_bump_mask_only:
        bookmark_x = loc.x
        for i, ch in enumerate(tex.channels):

            loc.x = bookmark_x
            loc.y = bookmarks_ys[i]

            rearrange_mask_ramp_nodes(tree, ch, loc)

            if loc.x > farthest_x: farthest_x = loc.x

        loc.x = farthest_x
        loc.y = 0

    bookmark_x = loc.x

    # Channel blends
    for i, ch in enumerate(tex.channels):

        loc.x = bookmark_x
        loc.y = bookmarks_ys[i]

        if check_set_node_loc(tree, ch.intensity_multiplier, loc):
            loc.x += 200.0

        if bump_ch and flip_bump and not bump_ch.mask_bump_mask_only:
            rearrange_mask_ramp_nodes(tree, ch, loc)

        if check_set_node_loc(tree, ch.intensity, loc):
            loc.x += 200.0

        if check_set_node_loc(tree, ch.normal_flip, loc):
            loc.x += 200.0

        if check_set_node_loc(tree, ch.blend, loc):
            loc.x += 250

        if loc.x > farthest_x: farthest_x = loc.x

    loc.x = farthest_x
    loc.y = mid_y
    check_set_node_loc(tree, tex.end, loc)

    # Back to source nodes
    loc = Vector((0, mid_y))

    if tex.source_group != '' and check_set_node_loc(tree, tex.source_group, loc):
        rearrange_source_tree_nodes(tex)
        loc.y -= 140

    elif check_set_node_loc(tree, tex.source, loc):
        loc.y -= 260

    if check_set_node_loc(tree, tex.solid_alpha, loc):
        loc.y -= 90

    #if check_set_node_loc(tree, tex.uv_map, loc):
    #    loc.y -= 115

    if check_set_node_loc(tree, tex.uv_attr, loc):
        loc.y -= 140

    if check_set_node_loc(tree, tex.texcoord, loc):
        loc.y -= 240

    if check_set_node_loc(tree, tex.tangent, loc):
        loc.y -= 160

    #if check_set_node_loc(tree, tex.hacky_tangent, loc):
    #    loc.y -= 160

    if check_set_node_loc(tree, tex.bitangent, loc):
        loc.y -= 160

    if check_set_node_loc(tree, tex.geometry, loc):
        #loc.y += 160
        pass

    rearrange_tex_frame_nodes(tex)

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

    # Start nodes
    for i, channel in enumerate(tl.channels):

        bookmark_y = loc.y
        loc.x = ori_x

        # Start nodes
        check_set_node_loc(group_tree, channel.start_linear, loc)
        check_set_node_loc(group_tree, channel.start_normal_filter, loc)

        # Start entry
        loc.x += 200
        loc.y -= 35
        check_set_node_loc(group_tree, channel.start_entry, loc)

        loc.y -= 35
        check_set_node_loc(group_tree, channel.start_alpha_entry, loc)

        loc.y = bookmark_y

        if channel.type == 'RGB':
            loc.y -= 165
        elif channel.type == 'VALUE':
            loc.y -= 220
        elif channel.type == 'NORMAL':
            loc.y -= 175

    # Rearrange solid alpha node
    if len(tl.channels) > 0:
        loc.y += 30
    loc.x = ori_x
    check_set_node_loc(group_tree, tl.solid_alpha, loc)

    #if len(tl.textures) == 0 and len(tl.channels) == 0:
    #    loc.x = ori_x + 200.0
    if len(tl.textures) == 0:
        loc.x = ori_x + 300.0
    else: 
        loc.x = ori_x + 280.0
    ori_x = loc.x
    loc.y = 0.0

    # Texture nodes
    for i, t in enumerate(reversed(tl.textures)):

        check_set_node_loc(group_tree, t.group_node, loc)

        if i == len(tl.textures)-1:
            loc.x += 220
        else: loc.x += 190

    ori_x = loc.x
    farthest_x = loc.x

    # End nodes
    for i, channel in enumerate(tl.channels):

        loc.x = ori_x
        bookmark_y = loc.y
        loc.y -= 35.0

        check_set_node_loc(group_tree, channel.end_entry, loc)

        loc.y -= 35.0
        check_set_node_loc(group_tree, channel.end_alpha_entry, loc)

        loc.x += 120.0
        loc.y = bookmark_y
        loc.y -= 35

        check_set_node_loc(group_tree, channel.start_rgb, loc)

        loc.y -= 35
        check_set_node_loc(group_tree, channel.start_alpha, loc)

        loc.x += 70
        loc.y = bookmark_y

        loc, offset_y = arrange_modifier_nodes(group_tree, channel, loc, 
                is_value = channel.type == 'VALUE', return_y_offset = True)
        loc.y -= 35

        check_set_node_loc(group_tree, channel.end_rgb, loc)

        loc.y -= 35
        check_set_node_loc(group_tree, channel.end_alpha, loc)

        loc.x += 100
        loc.y = bookmark_y

        if check_set_node_loc(group_tree, channel.end_linear, loc):
            loc.x += 200

        if loc.x > farthest_x: farthest_x = loc.x

        if offset_y < default_y_offsets[channel.type]:
            offset_y = default_y_offsets[channel.type]

        loc.y -= offset_y

        if i+1 < len(tl.channels):
            next_ch = tl.channels[i+1]
            if next_ch.type == 'NORMAL':
                loc.y += 25
            if len(next_ch.modifiers) > 0:
                loc.y -= 35

    loc.x = farthest_x
    loc.y = 0.0

    # End node
    check_set_node_loc(group_tree, tl.end, loc)

    # Rearrange frames
    rearrange_tl_frame_nodes(group_tree)

