import bpy
from .common import *
from .subtree import *
from . import lib

def get_transition_fine_bump_distance(distance, is_curved=False):
    if is_curved:
        scale = 20
    else: scale = 100
    #if mask.type == 'IMAGE':
    #    mask_tree = get_mask_tree(mask)
    #    source = mask_tree.nodes.get(mask.source)
    #    image = source.image
    #    if image: scale = image.size[0] / 10

    #return -1.0 * distance * scale
    return distance * scale

def set_transition_ramp_and_intensity_multiplier(tree, bump_ch, ch):
    if ch == bump_ch: return

    if bump_ch.transition_bump_flip: #or layer.type=='BACKGROUND':
        tr_ramp_mul = bump_ch.transition_bump_value
        tr_im_mul = bump_ch.transition_bump_second_edge_value
    else: 
        tr_ramp_mul = bump_ch.transition_bump_second_edge_value
        tr_im_mul = bump_ch.transition_bump_value

    tr_ramp = tree.nodes.get(ch.tr_ramp)
    if tr_ramp:
        tr_ramp.inputs['Multiplier'].default_value = 1.0 + (tr_ramp_mul - 1.0) * ch.transition_bump_second_fac

    im = tree.nodes.get(ch.intensity_multiplier)
    im_val = 1.0 + (tr_im_mul - 1.0) * ch.transition_bump_fac
    if not im: im = lib.new_intensity_multiplier_node(tree, ch, 'intensity_multiplier')
    im.inputs[1].default_value = im_val

    # Invert other intensity multipler if mask bump flip active
    im.inputs['Invert'].default_value = 1.0 if bump_ch.transition_bump_flip else 0.0

def check_transition_bump_influences_to_other_channels(layer, tree=None, target_ch = None):

    yp = layer.id_data.yp

    if not tree: tree = get_tree(layer)

    # Trying to get bump channel
    bump_ch = get_transition_bump_channel(layer)

    # Add intensity multiplier to other channel mask
    for i, c in enumerate(layer.channels):

        # NOTE: Bump channel supposed to be already had a mask intensity multipler
        if c == bump_ch: continue

        # If target channel is set, its the only one will be processed
        if target_ch and target_ch != c: continue

        # Transition AO update
        check_transition_ao_nodes(tree, layer, c, bump_ch)

        # Transition Ramp update
        check_transition_ramp_nodes(tree, layer, c)

        # Remove node if channel is disabled
        #if yp.disable_quick_toggle and not c.enable: 
        if not c.enable: 
            remove_node(tree, c, 'intensity_multiplier')
            continue

        if bump_ch: set_transition_ramp_and_intensity_multiplier(tree, bump_ch, c)

def get_transition_ao_intensity(ch):
    return ch.transition_ao_intensity * ch.intensity_value if not ch.transition_ao_intensity_unlink else ch.transition_ao_intensity

def check_transition_ao_nodes(tree, layer, ch, bump_ch=None):

    yp = layer.id_data.yp

    #if (not bump_ch or not ch.enable_transition_ao) or (yp.disable_quick_toggle and not ch.enable):
    if (not bump_ch or not ch.enable_transition_ao) or not ch.enable:
        remove_node(tree, ch, 'tao')

    elif bump_ch != ch and ch.enable_transition_ao:

        yp = ch.id_data.yp
        match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
        root_ch = yp.channels[int(match.group(2))]

        #if layer.type == 'BACKGROUND' and ch.transition_ao_blend_type == 'MIX':
        if layer.type == 'BACKGROUND' and bump_ch.transition_bump_flip and ch.transition_ao_blend_type == 'MIX':

            tao, dirty = replace_new_node(tree, ch, 'tao', 'ShaderNodeGroup', 
                    'Transition AO', lib.TRANSITION_AO_BG_MIX, return_status=True)
            if dirty: duplicate_lib_node_tree(tao)

        #elif layer.type == 'BACKGROUND' or bump_ch.transition_bump_flip:
        elif bump_ch.transition_bump_flip:

            tao, dirty = replace_new_node(tree, ch, 'tao', 'ShaderNodeGroup', 
                    'Transition AO', lib.TRANSITION_AO_FLIP, return_status=True)
            if dirty: duplicate_lib_node_tree(tao)

        elif ch.transition_ao_blend_type == 'MIX' and (
                layer.parent_idx != -1 or (root_ch.type == 'RGB' and root_ch.enable_alpha)):
            tao = replace_new_node(tree, ch, 'tao', 
                    'ShaderNodeGroup', 'Transition AO', lib.TRANSITION_AO_STRAIGHT_OVER)

        else:
            tao, dirty = replace_new_node(tree, ch, 'tao', 'ShaderNodeGroup', 
                    'Transition AO', lib.TRANSITION_AO, return_status=True)
            if dirty: duplicate_lib_node_tree(tao)

        # Blend type
        ao_blend = tao.node_tree.nodes.get('_BLEND')
        if ao_blend and ao_blend.blend_type != ch.transition_ao_blend_type:
            ao_blend.blend_type = ch.transition_ao_blend_type

        col = (ch.transition_ao_color.r, ch.transition_ao_color.g, ch.transition_ao_color.b, 1.0)
        tao.inputs['AO Color'].default_value = col

        tao.inputs['Power'].default_value = ch.transition_ao_power

        mute = not layer.enable or not ch.enable
        tao.inputs['Intensity'].default_value = 0.0 if mute else get_transition_ao_intensity(ch)

        tao.inputs['Exclude Inside'].default_value = 1.0 - ch.transition_ao_inside_intensity

        if root_ch.colorspace == 'SRGB':
            tao.inputs['Gamma'].default_value = 1.0/GAMMA
        else: tao.inputs['Gamma'].default_value = 1.0

def save_ramp(tree, ch):
    tr_ramp = tree.nodes.get(ch.tr_ramp)
    if not tr_ramp or tr_ramp.type != 'GROUP': return

    ramp = tr_ramp.node_tree.nodes.get('_RAMP')
    cache_ramp = tree.nodes.get(ch.cache_ramp)

    if not cache_ramp:
        cache_ramp = new_node(tree, ch, 'cache_ramp', 'ShaderNodeValToRGB')

    copy_node_props(ramp, cache_ramp)

def load_ramp(tree, ch):
    tr_ramp = tree.nodes.get(ch.tr_ramp)
    if not tr_ramp: return

    ramp = tr_ramp.node_tree.nodes.get('_RAMP')

    cache_ramp = tree.nodes.get(ch.cache_ramp)
    if cache_ramp:
        copy_node_props(cache_ramp, ramp)

def set_ramp_intensity_value(tree, layer, ch):

    mute = not ch.enable or not layer.enable

    tr_ramp_blend = tree.nodes.get(ch.tr_ramp_blend)
    if tr_ramp_blend:
        if ch.transition_ramp_intensity_unlink:
            intensity_value = ch.transition_ramp_intensity_value
        else: intensity_value = ch.transition_ramp_intensity_value * ch.intensity_value
        tr_ramp_blend.inputs['Intensity'].default_value = 0.0 if mute else intensity_value
    
    tr_ramp = tree.nodes.get(ch.tr_ramp)
    if tr_ramp and 'Intensity' in tr_ramp.inputs:
        tr_ramp.inputs['Intensity'].default_value = 0.0 if mute else ch.transition_ramp_intensity_value

def set_transition_ramp_nodes(tree, layer, ch):

    yp = ch.id_data.yp
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
    root_ch = yp.channels[int(match.group(2))]

    bump_ch = get_transition_bump_channel(layer)

    # Save previous ramp to cache
    save_ramp(tree, ch)

    #if bump_ch and (bump_ch.transition_bump_flip or layer.type == 'BACKGROUND'):
    if bump_ch and bump_ch.transition_bump_flip:

        tr_ramp, dirty = replace_new_node(tree, ch, 'tr_ramp', 
                'ShaderNodeGroup', 'Transition Ramp', lib.RAMP_FLIP, return_status=True)
        if dirty: duplicate_lib_node_tree(tr_ramp)

        if (ch.transition_ramp_blend_type == 'MIX' and 
                ((root_ch.type == 'RGB' and root_ch.enable_alpha) or layer.parent_idx != -1)):
            tr_ramp_blend = replace_new_node(tree, ch, 'tr_ramp_blend', 
                    'ShaderNodeGroup', 'Transition Ramp Blend', lib.RAMP_FLIP_STRAIGHT_OVER_BLEND)
        else:
            tr_ramp_blend, dirty = replace_new_node(tree, ch, 'tr_ramp_blend', 
                    'ShaderNodeGroup', 'Transition Ramp Blend', lib.RAMP_FLIP_BLEND, return_status=True)
            if dirty: duplicate_lib_node_tree(tr_ramp_blend)

            # Get blend node
            ramp_blend = tr_ramp_blend.node_tree.nodes.get('_BLEND')
            ramp_blend.blend_type = ch.transition_ramp_blend_type

    else:
        if layer.type == 'BACKGROUND' and ch.transition_ramp_blend_type == 'MIX':
            if ch.transition_ramp_intensity_unlink:
                tr_ramp, dirty = replace_new_node(tree, ch, 'tr_ramp', 
                        'ShaderNodeGroup', 'Transition Ramp', lib.RAMP_BG_MIX_UNLINK, return_status=True)
            elif layer.parent_idx != -1:
                tr_ramp, dirty = replace_new_node(tree, ch, 'tr_ramp', 
                        'ShaderNodeGroup', 'Transition Ramp', lib.RAMP_BG_MIX_CHILD, return_status=True)
            else:
                tr_ramp, dirty = replace_new_node(tree, ch, 'tr_ramp', 
                        'ShaderNodeGroup', 'Transition Ramp', lib.RAMP_BG_MIX, return_status=True)
        elif ch.transition_ramp_intensity_unlink and ch.transition_ramp_blend_type == 'MIX':
            tr_ramp, dirty = replace_new_node(tree, ch, 'tr_ramp', 
                    'ShaderNodeGroup', 'Transition Ramp', lib.RAMP_STRAIGHT_OVER, return_status=True)
        else:
            tr_ramp, dirty = replace_new_node(tree, ch, 'tr_ramp', 
                    'ShaderNodeGroup', 'Transition Ramp', lib.RAMP, return_status=True)

        if dirty: duplicate_lib_node_tree(tr_ramp)

        # Get blend node
        ramp_blend = tr_ramp.node_tree.nodes.get('_BLEND')
        if ramp_blend: ramp_blend.blend_type = ch.transition_ramp_blend_type

        remove_node(tree, ch, 'tr_ramp_blend')

    # Set intensity
    set_ramp_intensity_value(tree, layer, ch)

    # Load ramp from cache
    load_ramp(tree, ch)

    if bump_ch:
        #multiplier_val = 1.0 + (bump_ch.transition_bump_second_edge_value - 1.0) * ch.transition_bump_second_fac
        if bump_ch.transition_bump_flip:
            multiplier_val = 1.0 + (bump_ch.transition_bump_value - 1.0) * ch.transition_bump_second_fac
        else: multiplier_val = 1.0 + (bump_ch.transition_bump_second_edge_value - 1.0) * ch.transition_bump_second_fac
    else: multiplier_val = 1.0

    tr_ramp.inputs['Multiplier'].default_value = multiplier_val

    if root_ch.colorspace == 'SRGB':
        tr_ramp.inputs['Gamma'].default_value = 1.0/GAMMA
    else: tr_ramp.inputs['Gamma'].default_value = 1.0

def check_transition_ramp_nodes(tree, layer, ch):

    yp = layer.id_data.yp
    #if yp.disable_quick_toggle and not ch.enable:
    if not ch.enable:
        remove_transition_ramp_nodes(tree, ch)
        return

    if ch.enable_transition_ramp:
        set_transition_ramp_nodes(tree, layer, ch)
    else: remove_transition_ramp_nodes(tree, ch)

def remove_transition_ramp_nodes(tree, ch):
    # Save ramp first
    save_ramp(tree, ch)

    remove_node(tree, ch, 'tr_ramp')
    remove_node(tree, ch, 'tr_ramp_blend')

def save_transition_bump_falloff_cache(tree, ch):
    tb_falloff = tree.nodes.get(ch.tb_falloff)

    #if (ch.transition_bump_falloff_type != 'CURVE' or not ch.transition_bump_falloff or 
    #    not ch.enable_transition_bump or not ch.enable):

    if check_if_node_is_duplicated_from_lib(tb_falloff, lib.FALLOFF_CURVE):
        cache = tree.nodes.get(ch.cache_falloff_curve)
        if not cache:
            cache = new_node(tree, ch, 'cache_falloff_curve', 'ShaderNodeRGBCurve', 'Falloff Curve Cache')
        curve_ref = tb_falloff.node_tree.nodes.get('_curve')
        copy_node_props(curve_ref, cache)
    elif check_if_node_is_duplicated_from_lib(tb_falloff, lib.FALLOFF_CURVE_SMOOTH):
        cache = tree.nodes.get(ch.cache_falloff_curve)
        if not cache:
            cache = new_node(tree, ch, 'cache_falloff_curve', 'ShaderNodeRGBCurve', 'Falloff Curve Cache')
        ori = tb_falloff.node_tree.nodes.get('_original')
        curve_ref = ori.node_tree.nodes.get('_curve')
        copy_node_props(curve_ref, cache)

def check_transition_bump_falloff(layer, tree):

    yp = layer.id_data.yp

    trans_bump = get_transition_bump_channel(layer)
    if not trans_bump: return

    root_ch = [yp.channels[i] for i, ch in enumerate(layer.channels) if ch == trans_bump][0]
    ch = trans_bump

    save_transition_bump_falloff_cache(tree, ch)

    # Transition bump falloff
    if ch.transition_bump_falloff:

        # Emulated curve without actual curve
        if ch.transition_bump_falloff_type == 'EMULATED_CURVE':

            if root_ch.enable_smooth_bump:
                tb_falloff = replace_new_node(tree, ch, 'tb_falloff', 'ShaderNodeGroup', 'Falloff', 
                        lib.EMULATED_CURVE_SMOOTH, hard_replace=True)
            else:
                tb_falloff = replace_new_node(tree, ch, 'tb_falloff', 'ShaderNodeGroup', 'Falloff', 
                        lib.EMULATED_CURVE, hard_replace=True)

            tb_falloff.inputs['Fac'].default_value = get_transition_bump_falloff_emulated_curve_value(ch)

        elif ch.transition_bump_falloff_type == 'CURVE':
            tb_falloff = ori = tree.nodes.get(ch.tb_falloff)
            if root_ch.enable_smooth_bump:

                if not check_if_node_is_duplicated_from_lib(tb_falloff, lib.FALLOFF_CURVE_SMOOTH):

                    tb_falloff = replace_new_node(tree, ch, 'tb_falloff', 'ShaderNodeGroup', 'Falloff', 
                            lib.FALLOFF_CURVE_SMOOTH, hard_replace=True)
                    duplicate_lib_node_tree(tb_falloff)

                    # Duplicate group inside group
                    ori = tb_falloff.node_tree.nodes.get('_original')
                    if not check_if_node_is_duplicated_from_lib(ori, lib.FALLOFF_CURVE):
                        duplicate_lib_node_tree(ori)

                    # Use duplicated group to other directions
                    for n in tb_falloff.node_tree.nodes:
                        if n.type == 'GROUP' and n != ori:
                            prev_tree = n.node_tree
                            n.node_tree = ori.node_tree
                            if prev_tree and prev_tree.users == 0: bpy.data.node_groups.remove(prev_tree)

                    # Check cached curve
                    cache = tree.nodes.get(ch.cache_falloff_curve)
                    if cache:
                        curve = ori.node_tree.nodes.get('_curve')
                        copy_node_props(cache, curve)
                        remove_node(tree, ch, 'cache_falloff_curve')
                else:
                    ori = tb_falloff.node_tree.nodes.get('_original')

            elif not check_if_node_is_duplicated_from_lib(tb_falloff, lib.FALLOFF_CURVE):

                tb_falloff = ori = replace_new_node(tree, ch, 'tb_falloff', 'ShaderNodeGroup', 'Falloff', 
                        lib.FALLOFF_CURVE, hard_replace=True)
                duplicate_lib_node_tree(tb_falloff)

                # Check cached curve
                cache = tree.nodes.get(ch.cache_falloff_curve)
                if cache:
                    curve = tb_falloff.node_tree.nodes.get('_curve')
                    copy_node_props(cache, curve)
                    remove_node(tree, ch, 'cache_falloff_curve')

            inv0 = ori.node_tree.nodes.get('_inverse_0')
            inv1 = ori.node_tree.nodes.get('_inverse_1')

            inv0.mute = not ch.transition_bump_flip
            inv1.mute = not ch.transition_bump_flip

    else:
        remove_node(tree, ch, 'tb_falloff')

    #if ch.transition_bump_falloff and root_ch.enable_smooth_bump:
    #    for d in neighbor_directions:

    #        if ch.transition_bump_falloff_type == 'EMULATED_CURVE':
    #            tbf = replace_new_node(tree, ch, 'tb_falloff_' + d, 'ShaderNodeGroup', 'Falloff ' + d, 
    #                    lib.EMULATED_CURVE, hard_replace=True)
    #            tbf.inputs[1].default_value = get_transition_bump_falloff_emulated_curve_value(ch)

    #        elif ch.transition_bump_falloff_type == 'CURVE':
    #            tbf = replace_new_node(tree, ch, 'tb_falloff_' + d, 'ShaderNodeGroup', 'Falloff ' + d, 
    #                    tb_falloff.node_tree.name, hard_replace=True)
    #else:
    #    for d in neighbor_directions:
    #        remove_node(tree, ch, 'tb_falloff_' + d)

def check_transition_bump_nodes(layer, tree, ch):

    yp = layer.id_data.yp
    ch_index = get_layer_channel_index(layer, ch)
    root_ch = yp.channels[ch_index]

    if ch.enable_transition_bump and ch.enable:
        set_transition_bump_nodes(layer, tree, ch, ch_index)
    else: remove_transition_bump_nodes(layer, tree, ch, ch_index)

    # Add intensity multiplier to other channel
    check_transition_bump_influences_to_other_channels(layer, tree)

    # Dealing with mask sources
    #check_mask_source_tree(layer) #, ch)

    # Set mask mix nodes
    #check_mask_mix_nodes(layer, tree)

    # Update transition bump falloff
    check_transition_bump_falloff(layer, tree)

    # Check bump base
    check_create_spread_alpha(layer, tree, root_ch, ch)

    # Trigger normal channel update
    #ch.normal_map_type = ch.normal_map_type
    #update_disp_scale_node(tree, root_ch, ch)
    update_displacement_height_ratio(root_ch)

    # Check normal map nodes
    check_channel_normal_map_nodes(tree, layer, root_ch, ch)

    # Check extra alpha
    check_extra_alpha(layer)
    
def set_transition_bump_nodes(layer, tree, ch, ch_index):

    yp = layer.id_data.yp
    root_ch = yp.channels[ch_index]

    for i, c in enumerate(layer.channels):
        if yp.channels[i].type == 'NORMAL' and c.enable_transition_bump and c != ch:
            # Disable this mask bump if other channal already use mask bump
            if c.enable:
                yp.halt_update = True
                ch.enable_transition_bump = False
                yp.halt_update = False
                return
            # Disable other mask bump if other channal aren't enabled
            else:
                yp.halt_update = True
                c.enable_transition_bump = False
                yp.halt_update = False

    #if root_ch.enable_smooth_bump:
    #    remove_node(tree, ch, 'tb_bump_flip')
    #else:
    #    tb_bump_flip = replace_new_node(tree, ch, 'tb_bump_flip', 'ShaderNodeGroup', 
    #            'Transition Bump Backface Flip', lib.FLIP_BACKFACE_BUMP)

    #    set_bump_backface_flip(tb_bump_flip, yp.enable_backface_always_up)

    # Add inverse
    tb_inverse = tree.nodes.get(ch.tb_inverse)
    if not tb_inverse:
        tb_inverse = new_node(tree, ch, 'tb_inverse', 'ShaderNodeMath', 'Transition Bump Inverse')
        tb_inverse.operation = 'SUBTRACT'
        tb_inverse.inputs[0].default_value = 1.0

    tb_intensity_multiplier = tree.nodes.get(ch.tb_intensity_multiplier)
    if not tb_intensity_multiplier:
        tb_intensity_multiplier = lib.new_intensity_multiplier_node(tree, ch, 
                'tb_intensity_multiplier', ch.transition_bump_value)

    intensity_multiplier = tree.nodes.get(ch.intensity_multiplier)
    if not intensity_multiplier:
        intensity_multiplier = lib.new_intensity_multiplier_node(tree, ch, 
                'intensity_multiplier', ch.transition_bump_value)

    if ch.transition_bump_flip or layer.type == 'BACKGROUND':
        #intensity_multiplier.inputs[1].default_value = ch.transition_bump_second_edge_value
        #tb_intensity_multiplier.inputs[1].default_value = ch.transition_bump_value
        set_default_value(intensity_multiplier, 'Sharpen', 0.0)
        set_default_value(tb_intensity_multiplier, 'Sharpen', 1.0)
    else:
        #intensity_multiplier.inputs[1].default_value = ch.transition_bump_value
        #tb_intensity_multiplier.inputs[1].default_value = ch.transition_bump_second_edge_value
        set_default_value(intensity_multiplier, 'Sharpen', 1.0)
        set_default_value(tb_intensity_multiplier, 'Sharpen', 0.0)

    set_default_value(intensity_multiplier, 1, ch.transition_bump_value)
    set_default_value(tb_intensity_multiplier, 1, ch.transition_bump_second_edge_value)

def remove_transition_bump_influence_nodes_to_other_channels(layer, tree):
    # Delete intensity multiplier from ramp
    for c in layer.channels:
        remove_node(tree, c, 'intensity_multiplier')

        # Remove transition ao related nodes
        check_transition_ao_nodes(tree, layer, c)

def remove_transition_bump_nodes(layer, tree, ch, ch_index):

    save_transition_bump_falloff_cache(tree, ch)

    disable_layer_source_tree(layer, False)
    Modifier.disable_modifiers_tree(ch)

    remove_node(tree, ch, 'intensity_multiplier')
    remove_node(tree, ch, 'tb_bump')
    remove_node(tree, ch, 'tb_bump_flip')
    remove_node(tree, ch, 'tb_inverse')
    remove_node(tree, ch, 'tb_intensity_multiplier')

    remove_node(tree, ch, 'tb_falloff')
    remove_node(tree, ch, 'tb_falloff_n')
    remove_node(tree, ch, 'tb_falloff_s')
    remove_node(tree, ch, 'tb_falloff_e')
    remove_node(tree, ch, 'tb_falloff_w')

    # Check mask related nodes
    check_mask_source_tree(layer)
    check_mask_mix_nodes(layer)

    remove_transition_bump_influence_nodes_to_other_channels(layer, tree)

