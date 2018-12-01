import bpy
from bpy.props import *
from .common import *
from .node_connections import *
from .node_arrangements import *
from .subtree import *

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

def check_transition_bump_influences_to_other_channels(tex, tree=None, target_ch = None):

    if not tree: tree = get_tree(tex)

    # Trying to get bump channel
    bump_ch = get_transition_bump_channel(tex)

    # Transition AO update
    for i, c in enumerate(tex.channels):
        check_transition_ao_nodes(tree, tex, c, bump_ch)

    # Intensity multiplier is only created if transition bump channel is available
    #if not bump_ch: 
        #remove_transition_bump_influence_nodes_to_other_channels(tex, tree)
        #return

    # Add intensity multiplier to other channel mask
    for i, c in enumerate(tex.channels):

        # If target channel is set, its the only one will be processed
        if target_ch and target_ch != c: continue

        # NOTE: Bump channel supposed to be already had a mask intensity multipler
        if c == bump_ch: continue

        check_transition_ramp_nodes(tree, tex, c)

        if bump_ch:
            im = tree.nodes.get(c.intensity_multiplier)
            if not im:
                im = lib.new_intensity_multiplier_node(tree, c, 'intensity_multiplier', 
                        1.0 + (bump_ch.transition_bump_value - 1.0) * c.transition_bump_fac)

            # Invert other intensity multipler if mask bump flip active
            if bump_ch.transition_bump_flip or tex.type == 'BACKGROUND':
            #if bump_ch.transition_bump_flip:
                im.inputs['Invert'].default_value = 1.0
            else: im.inputs['Invert'].default_value = 0.0

def get_transition_ao_intensity(ch):
    return ch.transition_ao_intensity * ch.intensity_value if not ch.transition_ao_intensity_unlink else ch.transition_ao_intensity

def check_transition_ao_nodes(tree, tex, ch, bump_ch=None):

    if not bump_ch or not ch.enable_transition_ao:
        remove_node(tree, ch, 'tao')

    elif bump_ch != ch and ch.enable_transition_ao:

        tl = ch.id_data.tl
        match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
        root_ch = tl.channels[int(match.group(2))]

        if tex.type == 'BACKGROUND' and ch.transition_ao_blend_type == 'MIX':
        #if tex.type == 'BACKGROUND' and bump_ch.transition_bump_flip and ch.transition_ao_blend_type == 'MIX':

            tao, replaced = replace_new_node(tree, ch, 'tao', 'ShaderNodeGroup', 
                    'Transition AO', lib.TRANSITION_AO_BG_MIX, return_status=True)
            if replaced: duplicate_lib_node_tree(tao)

        elif tex.type == 'BACKGROUND' or bump_ch.transition_bump_flip:
        #elif bump_ch.transition_bump_flip:

            tao, replaced = replace_new_node(tree, ch, 'tao', 'ShaderNodeGroup', 
                    'Transition AO', lib.TRANSITION_AO_FLIP, return_status=True)
            if replaced: duplicate_lib_node_tree(tao)

        elif ch.transition_ao_blend_type == 'MIX' and (
                tex.parent_idx != -1 or (root_ch.type == 'RGB' and root_ch.enable_alpha)):
            tao = replace_new_node(tree, ch, 'tao', 
                    'ShaderNodeGroup', 'Transition AO', lib.TRANSITION_AO_STRAIGHT_OVER)

        else:
            tao, replaced = replace_new_node(tree, ch, 'tao', 'ShaderNodeGroup', 
                    'Transition AO', lib.TRANSITION_AO, return_status=True)
            if replaced: duplicate_lib_node_tree(tao)

        # Blend type
        ao_blend = tao.node_tree.nodes.get('_BLEND')
        if ao_blend and ao_blend.blend_type != ch.transition_ao_blend_type:
            ao_blend.blend_type = ch.transition_ao_blend_type

        col = (ch.transition_ao_color.r, ch.transition_ao_color.g, ch.transition_ao_color.b, 1.0)
        tao.inputs['AO Color'].default_value = col

        tao.inputs['Power'].default_value = ch.transition_ao_power

        mute = not tex.enable or not ch.enable
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

def set_ramp_intensity_value(tree, tex, ch):

    mute = not ch.enable or not tex.enable

    tr_ramp_blend = tree.nodes.get(ch.tr_ramp_blend)
    if tr_ramp_blend:
        if ch.transition_ramp_intensity_unlink:
            intensity_value = ch.transition_ramp_intensity_value
        else: intensity_value = ch.transition_ramp_intensity_value * ch.intensity_value
        tr_ramp_blend.inputs['Intensity'].default_value = 0.0 if mute else intensity_value
    
    tr_ramp = tree.nodes.get(ch.tr_ramp)
    if tr_ramp and 'Intensity' in tr_ramp.inputs:
        tr_ramp.inputs['Intensity'].default_value = 0.0 if mute else ch.transition_ramp_intensity_value

def set_transition_ramp_nodes(tree, tex, ch):

    tl = ch.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
    root_ch = tl.channels[int(match.group(2))]

    bump_ch = get_transition_bump_channel(tex)

    # Save previous ramp to cache
    save_ramp(tree, ch)

    if bump_ch and (bump_ch.transition_bump_flip or tex.type == 'BACKGROUND'):
    #if bump_ch and bump_ch.transition_bump_flip:

        tr_ramp, replaced = replace_new_node(tree, ch, 'tr_ramp', 
                'ShaderNodeGroup', 'Transition Ramp', lib.RAMP_FLIP, return_status=True)
        if replaced: duplicate_lib_node_tree(tr_ramp)

        if (ch.transition_ramp_blend_type == 'MIX' and 
                ((root_ch.type == 'RGB' and root_ch.enable_alpha) or tex.parent_idx != -1)):
            tr_ramp_blend = replace_new_node(tree, ch, 'tr_ramp_blend', 
                    'ShaderNodeGroup', 'Transition Ramp Blend', lib.RAMP_FLIP_STRAIGHT_OVER_BLEND)
        else:
            tr_ramp_blend, replaced = replace_new_node(tree, ch, 'tr_ramp_blend', 
                    'ShaderNodeGroup', 'Transition Ramp Blend', lib.RAMP_FLIP_BLEND, return_status=True)
            if replaced: duplicate_lib_node_tree(tr_ramp_blend)

            # Get blend node
            ramp_blend = tr_ramp_blend.node_tree.nodes.get('_BLEND')
            ramp_blend.blend_type = ch.transition_ramp_blend_type

    else:

        if ch.transition_ramp_intensity_unlink and ch.transition_ramp_blend_type == 'MIX':
            tr_ramp, replaced = replace_new_node(tree, ch, 'tr_ramp', 
                    'ShaderNodeGroup', 'Transition Ramp', lib.RAMP_STRAIGHT_OVER, return_status=True)
        else:
            tr_ramp, replaced = replace_new_node(tree, ch, 'tr_ramp', 
                    'ShaderNodeGroup', 'Transition Ramp', lib.RAMP, return_status=True)

        if replaced: duplicate_lib_node_tree(tr_ramp)

        # Get blend node
        ramp_blend = tr_ramp.node_tree.nodes.get('_BLEND')
        if ramp_blend: ramp_blend.blend_type = ch.transition_ramp_blend_type

        remove_node(tree, ch, 'tr_ramp_blend')

    # Set intensity
    set_ramp_intensity_value(tree, tex, ch)

    # Load ramp from cache
    load_ramp(tree, ch)

    if bump_ch:
        multiplier_val = 1.0 + (bump_ch.transition_bump_second_edge_value - 1.0) * ch.transition_bump_second_fac
    else: multiplier_val = 1.0

    tr_ramp.inputs['Multiplier'].default_value = multiplier_val

    if root_ch.colorspace == 'SRGB':
        tr_ramp.inputs['Gamma'].default_value = 1.0/GAMMA
    else: tr_ramp.inputs['Gamma'].default_value = 1.0

def check_transition_ramp_nodes(tree, tex, ch):

    if ch.enable_transition_ramp:
        set_transition_ramp_nodes(tree, tex, ch)
    else: remove_transition_ramp_nodes(tree, ch)

def remove_transition_ramp_nodes(tree, ch):
    # Save ramp first
    save_ramp(tree, ch)

    remove_node(tree, ch, 'tr_ramp')
    remove_node(tree, ch, 'tr_ramp_blend')

def check_transition_bump_nodes(tex, tree, ch, ch_index):

    if ch.enable_transition_bump and ch.enable:
        set_transition_bump_nodes(tex, tree, ch, ch_index)
    else: remove_transition_bump_nodes(tex, tree, ch, ch_index)

    # Add intensity multiplier to other channel
    check_transition_bump_influences_to_other_channels(tex, tree)

    # Set mask multiply nodes
    check_mask_multiply_nodes(tex, tree)

    # Check bump base
    check_create_bump_base(tex, tree, ch)

    # Trigger normal channel update
    #ch.normal_map_type = ch.normal_map_type
    
    rearrange_tex_nodes(tex)
    reconnect_tex_nodes(tex) #, mod_reconnect=True)

def set_transition_bump_nodes(tex, tree, ch, ch_index):

    tl = tex.id_data.tl

    for i, c in enumerate(tex.channels):
        if tl.channels[i].type == 'NORMAL' and c.enable_transition_bump and c != ch:
            # Disable this mask bump if other channal already use mask bump
            if c.enable:
                tl.halt_update = True
                ch.enable_transition_bump = False
                tl.halt_update = False
                return
            # Disable other mask bump if other channal aren't enabled
            else:
                tl.halt_update = True
                c.enable_transition_bump = False
                tl.halt_update = False

    if ch.transition_bump_type == 'FINE_BUMP_MAP':

        enable_tex_source_tree(tex)
        Modifier.enable_modifiers_tree(ch)

        # Get fine bump
        tb_bump = replace_new_node(tree, ch, 'tb_bump', 'ShaderNodeGroup', 'Transition Fine Bump', lib.FINE_BUMP)

        if ch.transition_bump_flip or tex.type == 'BACKGROUND':
        #if ch.transition_bump_flip:
            tb_bump.inputs[0].default_value = -get_transition_fine_bump_distance(ch.transition_bump_distance)
        else: tb_bump.inputs[0].default_value = get_transition_fine_bump_distance(ch.transition_bump_distance)

    if ch.transition_bump_type == 'CURVED_BUMP_MAP':

        enable_tex_source_tree(tex)
        Modifier.enable_modifiers_tree(ch)

        if ch.transition_bump_flip or tex.type == 'BACKGROUND':
        #if ch.transition_bump_flip:
            tb_bump = replace_new_node(tree, ch, 'tb_bump', 'ShaderNodeGroup', 
                    'Transition Curved Bump', lib.FLIP_CURVED_FINE_BUMP)
        else: 
            tb_bump = replace_new_node(tree, ch, 'tb_bump', 'ShaderNodeGroup', 
                    'Transition Curved Bump', lib.CURVED_FINE_BUMP)

        if ch.transition_bump_flip or tex.type == 'BACKGROUND':
        #if ch.transition_bump_flip:
            tb_bump.inputs[0].default_value = -get_transition_fine_bump_distance(ch.transition_bump_distance, True)
        else: tb_bump.inputs[0].default_value = get_transition_fine_bump_distance(ch.transition_bump_distance, True)

        tb_bump.inputs['Offset'].default_value = ch.transition_bump_curved_offset

    if ch.transition_bump_type == 'BUMP_MAP':

        disable_tex_source_tree(tex, False)
        Modifier.disable_modifiers_tree(ch)

        # Get bump
        tb_bump = replace_new_node(tree, ch, 'tb_bump', 'ShaderNodeBump', 'Transition Bump')

        if ch.transition_bump_flip or tex.type == 'BACKGROUND':
        #if ch.transition_bump_flip:
            tb_bump.inputs[1].default_value = -ch.transition_bump_distance
        else: tb_bump.inputs[1].default_value = ch.transition_bump_distance

    # Crease stuff
    if ch.transition_bump_crease and not ch.transition_bump_flip and tex.type != 'BACKGROUND':
    #if ch.transition_bump_crease and not ch.transition_bump_flip:
        if ch.transition_bump_type == 'BUMP_MAP':
            tb_crease = replace_new_node(tree, ch, 'tb_crease', 'ShaderNodeBump', 'Transition Bump Crease')
            tb_crease.inputs[1].default_value = -ch.transition_bump_distance * ch.transition_bump_crease_factor
        else:
            tb_crease = replace_new_node(tree, ch, 'tb_crease', 'ShaderNodeGroup', 
                    'Transition Bump Crease', lib.FINE_BUMP)
            tb_crease.inputs[0].default_value = -get_transition_fine_bump_distance(ch.transition_bump_distance) * ch.transition_bump_crease_factor

        tb_crease_intensity = replace_new_node(tree, ch, 'tb_crease_intensity', 'ShaderNodeMath',
                    'Transition Bump Crease Intensity')
        tb_crease_intensity.operation = 'MULTIPLY'
        tb_crease_intensity.inputs[1].default_value = ch.intensity_value if tex.enable else 0.0

        tb_crease_mix = replace_new_node(tree, ch, 'tb_crease_mix', 'ShaderNodeGroup',
                    'Transition Bump Crease Mix', lib.OVERLAY_NORMAL)

    else:
        remove_node(tree, ch, 'tb_crease')
        remove_node(tree, ch, 'tb_crease_intensity')
        remove_node(tree, ch, 'tb_crease_mix')

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

    if ch.transition_bump_flip or tex.type == 'BACKGROUND':
    #if ch.transition_bump_flip:
        intensity_multiplier.inputs[1].default_value = ch.transition_bump_second_edge_value
        tb_intensity_multiplier.inputs[1].default_value = ch.transition_bump_value
        intensity_multiplier.inputs['Sharpen'].default_value = 0.0
        tb_intensity_multiplier.inputs['Sharpen'].default_value = 1.0
    else:
        intensity_multiplier.inputs[1].default_value = ch.transition_bump_value
        tb_intensity_multiplier.inputs[1].default_value = ch.transition_bump_second_edge_value
        intensity_multiplier.inputs['Sharpen'].default_value = 1.0
        tb_intensity_multiplier.inputs['Sharpen'].default_value = 0.0

    # Add vector mix
    tb_blend = tree.nodes.get(ch.tb_blend)
    if not tb_blend:
        tb_blend = new_node(tree, ch, 'tb_blend', 'ShaderNodeGroup', 'Transition Vector Blend')
        tb_blend.node_tree = get_node_tree_lib(lib.VECTOR_MIX)

    # Dealing with mask sources
    check_mask_source_tree(tex) #, ch)

def remove_transition_bump_influence_nodes_to_other_channels(tex, tree):
    # Delete intensity multiplier from ramp
    for c in tex.channels:
        remove_node(tree, c, 'intensity_multiplier')

        # Remove transition ao related nodes
        check_transition_ao_nodes(tree, tex, c)

def remove_transition_bump_nodes(tex, tree, ch, ch_index):

    disable_tex_source_tree(tex, False)
    Modifier.disable_modifiers_tree(ch)

    remove_node(tree, ch, 'intensity_multiplier')
    remove_node(tree, ch, 'tb_bump')
    remove_node(tree, ch, 'tb_inverse')
    remove_node(tree, ch, 'tb_intensity_multiplier')
    remove_node(tree, ch, 'tb_blend')

    remove_node(tree, ch, 'tb_crease')
    remove_node(tree, ch, 'tb_crease_intensity')
    remove_node(tree, ch, 'tb_crease_mix')

    # Check mask related nodes
    check_mask_source_tree(tex)
    check_mask_multiply_nodes(tex)

    remove_transition_bump_influence_nodes_to_other_channels(tex, tree)

def update_transition_ramp_intensity_value(self, context):
    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    tree = get_tree(tex)

    set_ramp_intensity_value(tree, tex, self)

def update_transition_bump_crease_factor(self, context):
    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    tree = get_tree(tex)
    ch = self

    tb_crease = tree.nodes.get(ch.tb_crease)
    if tb_crease:
        if ch.transition_bump_type == 'BUMP_MAP':
            tb_crease.inputs[1].default_value = -ch.transition_bump_distance * ch.transition_bump_crease_factor
        else: tb_crease.inputs[0].default_value = -get_transition_fine_bump_distance(ch.transition_bump_distance) * ch.transition_bump_crease_factor

def update_transition_bump_value(self, context):
    if not self.enable: return

    tl = self.id_data.tl
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    tree = get_tree(tex)
    ch = self

    intensity_multiplier = tree.nodes.get(ch.intensity_multiplier)
    tb_intensity_multiplier = tree.nodes.get(ch.tb_intensity_multiplier)

    if ch.transition_bump_flip or tex.type=='BACKGROUND':
    #if ch.transition_bump_flip:
        if intensity_multiplier:
            intensity_multiplier.inputs[1].default_value = ch.transition_bump_second_edge_value
        if tb_intensity_multiplier:
            tb_intensity_multiplier.inputs[1].default_value = ch.transition_bump_value
    else:
        if intensity_multiplier:
            intensity_multiplier.inputs[1].default_value = ch.transition_bump_value
        if tb_intensity_multiplier:
            tb_intensity_multiplier.inputs[1].default_value = ch.transition_bump_second_edge_value

    for c in tex.channels:
        if c == ch: continue

        tr_ramp = tree.nodes.get(c.tr_ramp)
        if tr_ramp:
            tr_ramp.inputs['Multiplier'].default_value = 1.0 + (
                    ch.transition_bump_second_edge_value - 1.0) * c.transition_bump_second_fac

        im = tree.nodes.get(c.intensity_multiplier)
        if im: 
            im.inputs[1].default_value = 1.0 + (ch.transition_bump_value - 1.0) * c.transition_bump_fac

def update_transition_bump_distance(self, context):
    if not self.enable: return

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch_index = int(match.group(2))
    ch = self
    tree = get_tree(tex)

    tb_bump = tree.nodes.get(ch.tb_bump)
    if tb_bump:
        if ch.transition_bump_type == 'CURVED_BUMP_MAP':
            if ch.transition_bump_flip or tex.type=='BACKGROUND':
            #if ch.transition_bump_flip:
                tb_bump.inputs[0].default_value = -get_transition_fine_bump_distance(
                        ch.transition_bump_distance, True)
            else: tb_bump.inputs[0].default_value = get_transition_fine_bump_distance(
                    ch.transition_bump_distance, True)

        elif ch.transition_bump_type == 'FINE_BUMP_MAP':
            if ch.transition_bump_flip or tex.type=='BACKGROUND':
            #if ch.transition_bump_flip:
                tb_bump.inputs[0].default_value = -get_transition_fine_bump_distance(ch.transition_bump_distance)
            else: tb_bump.inputs[0].default_value = get_transition_fine_bump_distance(ch.transition_bump_distance)

        elif ch.transition_bump_type == 'BUMP_MAP':
            if ch.transition_bump_flip or tex.type=='BACKGROUND':
            #if ch.transition_bump_flip:
                tb_bump.inputs[1].default_value = -ch.transition_bump_distance
            else: tb_bump.inputs[1].default_value = ch.transition_bump_distance

    if ch.transition_bump_crease:
        tb_crease = tree.nodes.get(ch.tb_crease)
        if ch.transition_bump_type == 'BUMP_MAP':
            tb_crease.inputs[1].default_value = ch.transition_bump_crease_factor * -ch.transition_bump_distance
        else: tb_crease.inputs[0].default_value = ch.transition_bump_crease_factor * -get_transition_fine_bump_distance(ch.transition_bump_distance)

def update_transition_bump_chain(self, context):
    T = time.time()

    tl = self.id_data.tl
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    tree = get_tree(tex)
    ch = self

    #if ch.enable_transition_bump and ch.enable:

    check_mask_multiply_nodes(tex, tree)
    check_mask_source_tree(tex) #, ch)

    # Trigger normal channel update
    #ch.normal_map_type = ch.normal_map_type

    rearrange_tex_nodes(tex)
    reconnect_tex_nodes(tex) #, mod_reconnect=True)

    print('INFO: Transition bump chain is updated at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def update_transition_bump_curved_offset(self, context):

    tl = self.id_data.tl
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    tree = get_tree(tex)
    ch = self

    tb_bump = tree.nodes.get(ch.tb_bump)
    if tb_bump:
        tb_bump.inputs['Offset'].default_value = ch.transition_bump_curved_offset

def update_transition_bump_fac(self, context):

    tl = self.id_data.tl
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    tree = get_tree(tex)
    ch = self

    bump_ch = get_transition_bump_channel(tex)

    if ch != bump_ch:

        im = tree.nodes.get(ch.intensity_multiplier)
        if im: 
            im.inputs[1].default_value = 1.0 + (bump_ch.transition_bump_value - 1.0) * ch.transition_bump_fac

        tr_ramp = tree.nodes.get(ch.tr_ramp)
        if tr_ramp and bump_ch:
            tr_ramp.inputs['Multiplier'].default_value = 1.0 + (
                    bump_ch.transition_bump_second_edge_value - 1.0) * ch.transition_bump_second_fac

def update_transition_ao_intensity(self, context):

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch = self
    tree = get_tree(tex)

    mute = not tex.enable or not ch.enable

    tao = tree.nodes.get(ch.tao)
    if tao:
        tao.inputs['Intensity'].default_value = 0.0 if mute else get_transition_ao_intensity(ch)

def update_transition_ao_edge(self, context):

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch = self
    tree = get_tree(tex)

    bump_ch = get_transition_bump_channel(tex)

    tao = tree.nodes.get(ch.tao)
    if tao and bump_ch:
        tao.inputs['Power'].default_value = ch.transition_ao_power

def update_transition_ao_color(self, context):

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch = self
    tree = get_tree(tex)

    tao = tree.nodes.get(ch.tao)
    if tao:
        col = (ch.transition_ao_color.r, ch.transition_ao_color.g, ch.transition_ao_color.b, 1.0)
        tao.inputs['AO Color'].default_value = col

def update_transition_ao_exclude_inside(self, context):

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch = self
    tree = get_tree(tex)

    tao = tree.nodes.get(ch.tao)
    if tao:
        tao.inputs['Exclude Inside'].default_value = 1.0 - ch.transition_ao_inside_intensity

def show_transition(self, context, ttype):
    if not hasattr(context, 'parent'): 
        self.report({'ERROR'}, "Context is incorrect!")
        return {'CANCELLED'}

    tl = context.parent.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', context.parent.path_from_id())
    if not match: 
        self.report({'ERROR'}, "Context is incorrect!")
        return {'CANCELLED'}
    tex = tl.textures[int(match.group(1))]
    root_ch = tl.channels[int(match.group(2))]
    ch = context.parent

    bump_ch = get_transition_bump_channel(tex)

    if ttype == 'BUMP':

        if root_ch.type != 'NORMAL': 
            self.report({'ERROR'}, "Transition bump only works on Normal channel!")
            return {'CANCELLED'}

        if bump_ch and ch != bump_ch:
            self.report({'ERROR'}, "Transition bump already enabled on other channel!")
            return {'CANCELLED'}

        ch.show_transition_bump = True

        if ch.enable_transition_bump:
            self.report({'INFO'}, "Transition bump is already set!")
            return {'FINISHED'}

        ch.enable_transition_bump = True

        # Hide other channels transition bump
        for c in tex.channels:
            if c != ch:
                c.show_transition_bump = False

    elif ttype == 'RAMP':

        if root_ch.type == 'NORMAL': 
            self.report({'ERROR'}, "Transition ramp only works on color or value channel!")
            return {'CANCELLED'}

        ch.show_transition_ramp = True

        if ch.enable_transition_ramp:
            self.report({'INFO'}, "Transition ramp is already set!")
            return {'FINISHED'}

        ch.enable_transition_ramp = True

    elif ttype == 'AO':

        if root_ch.type == 'NORMAL': 
            self.report({'ERROR'}, "Transition AO only works on color or value channel!")
            return {'CANCELLED'}

        if not bump_ch:
            self.report({'ERROR'}, "Transition AO only works if there's transition bump enabled on other channel!")
            return {'CANCELLED'}

        ch.show_transition_ao = True

        if ch.enable_transition_ao:
            self.report({'INFO'}, "Transition AO is already set!")
            return {'FINISHED'}

        ch.enable_transition_ao = True

    # Expand channel content
    if hasattr(context, 'channel_ui'):
        context.channel_ui.expand_content = True

    return {'FINISHED'}

class YShowTransitionBump(bpy.types.Operator):
    """Use transition bump (This will affect other channels)"""
    bl_idname = "node.y_show_transition_bump"
    bl_label = "Show Transition Bump"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        return show_transition(self, context, ttype = 'BUMP')

class YShowTransitionRamp(bpy.types.Operator):
    """Use transition ramp (Works best if there's transition bump enabled on other channel)"""
    bl_idname = "node.y_show_transition_ramp"
    bl_label = "Show Transition Ramp"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        return show_transition(self, context, ttype = 'RAMP')

class YShowTransitionAO(bpy.types.Operator):
    """Use transition AO (Only works if there's transition bump enabled on other channel)"""
    bl_idname = "node.y_show_transition_ao"
    bl_label = "Show Transition AO"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        return show_transition(self, context, ttype = 'AO')

class YHideTransitionEffect(bpy.types.Operator):
    """Remove transition Effect"""
    bl_idname = "node.y_hide_transition_effect"
    bl_label = "Hide Transition Effect"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
            name = 'Type',
            items = (
                ('BUMP', 'Bump', ''),
                ('RAMP', 'Ramp', ''),
                ('AO', 'AO', ''),
                ),
            default = 'BUMP')

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):

        if not hasattr(context, 'parent'): 
            self.report({'ERROR'}, "Context is incorrect!")
            return {'CANCELLED'}

        tl = context.parent.id_data.tl
        match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', context.parent.path_from_id())
        if not match: 
            self.report({'ERROR'}, "Context is incorrect!")
            return {'CANCELLED'}
        tex = tl.textures[int(match.group(1))]
        root_ch = tl.channels[int(match.group(2))]
        ch = context.parent

        if self.type == 'BUMP' and root_ch.type != 'NORMAL':
            self.report({'ERROR'}, "Context is incorrect!")
            return {'CANCELLED'}

        if self.type != 'BUMP' and root_ch.type == 'NORMAL':
            self.report({'ERROR'}, "Context is incorrect!")
            return {'CANCELLED'}

        if self.type == 'BUMP':
            ch.enable_transition_bump = False
            ch.show_transition_bump = False
        elif self.type == 'RAMP':
            ch.enable_transition_ramp = False
            ch.show_transition_ramp = False
        else:
            ch.enable_transition_ao = False
            ch.show_transition_ao = False

        return {'FINISHED'}

def update_enable_transition_ao(self, context):
    T = time.time()

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch = self

    tree = get_tree(tex)

    # Get transition bump
    bump_ch = get_transition_bump_channel(tex)

    check_transition_ao_nodes(tree, tex, ch, bump_ch)

    # Update mask multiply
    check_mask_multiply_nodes(tex, tree)

    rearrange_tex_nodes(tex)
    reconnect_tex_nodes(tex)

    if ch.enable_transition_ao:
        print('INFO: Transition AO is enabled at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')
    else: print('INFO: Transition AO is disabled at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def update_enable_transition_ramp(self, context):
    T = time.time()

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch = self

    tree = get_tree(tex)

    check_transition_ramp_nodes(tree, tex, ch)

    # Update mask multiply
    check_mask_multiply_nodes(tex, tree)

    rearrange_tex_nodes(tex)
    reconnect_tex_nodes(tex)

    if ch.enable_transition_ramp:
        print('INFO: Transition ramp is enabled at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')
    else: print('INFO: Transition ramp is disabled at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def update_enable_transition_bump(self, context):
    T = time.time()

    tl = self.id_data.tl
    if tl.halt_update or not self.enable: return
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch_index = int(match.group(2))
    ch = self
    tree = get_tree(tex)

    check_transition_bump_nodes(tex, tree, ch, ch_index)

    if ch.enable_transition_bump:
        print('INFO: Transition bump is enabled at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')
    else: print('INFO: Transition bump is disabled at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def register():
    bpy.utils.register_class(YShowTransitionBump)
    bpy.utils.register_class(YShowTransitionRamp)
    bpy.utils.register_class(YShowTransitionAO)
    bpy.utils.register_class(YHideTransitionEffect)

def unregister():
    bpy.utils.unregister_class(YShowTransitionBump)
    bpy.utils.unregister_class(YShowTransitionRamp)
    bpy.utils.unregister_class(YShowTransitionAO)
    bpy.utils.unregister_class(YHideTransitionEffect)
