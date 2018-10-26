import bpy
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

def remove_transition_ramp_flip_nodes(tree, ch):
    remove_node(tree, ch, 'mr_alpha1')
    remove_node(tree, ch, 'mr_flip_hack')
    remove_node(tree, ch, 'mr_flip_blend')

def check_transition_ramp_flip_nodes(tex, tree, ch, bump_ch=None, rearrange=False):

    if bump_ch and (bump_ch.mask_bump_flip or tex.type == 'BACKGROUND'):
        mr_flip_hack = tree.nodes.get(ch.mr_flip_hack)
        if not mr_flip_hack:
            mr_flip_hack = new_node(tree, ch, 'mr_flip_hack', 'ShaderNodeMath', 
                    'Transition Ramp Flip Hack')
            mr_flip_hack.operation = 'POWER'
            rearrange = True

        # Flip bump is better be muted if intensity is maximum
        if ch.intensity_value < 1.0:
            mr_flip_hack.inputs[1].default_value = 1
        else: mr_flip_hack.inputs[1].default_value = 20

        mr_flip_blend = tree.nodes.get(ch.mr_flip_blend)
        if not mr_flip_blend:
            mr_flip_blend = new_node(tree, ch, 'mr_flip_blend', 'ShaderNodeMixRGB', 
                    'Transition Ramp Flip Blend')
            rearrange = True

        remove_node(tree, ch, 'mr_inverse')

    else:
        # Delete transition ramp flip nodes
        remove_transition_ramp_flip_nodes(tree, ch)

        # Add inverse node
        mr_inverse = tree.nodes.get(ch.mr_inverse)
        if not mr_inverse:
            mr_inverse = new_node(tree, ch, 'mr_inverse', 'ShaderNodeMath', 'Transition Ramp Inverse')
            mr_inverse.operation = 'SUBTRACT'
            mr_inverse.inputs[0].default_value = 1.0
            #mr_inverse.use_clamp = True
            rearrange = True

    return rearrange

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

        if c.enable_mask_ramp: 

            # Fix intensity value
            mr_intensity = tree.nodes.get(c.mr_intensity)
            if mr_intensity:
                if bump_ch and (bump_ch.mask_bump_flip or tex.type == 'BACKGROUND'):
                    mr_intensity.inputs[1].default_value = c.mask_ramp_intensity_value * c.intensity_value
                else: mr_intensity.inputs[1].default_value = c.mask_ramp_intensity_value

            # Flip mask bump related nodes
            check_transition_ramp_flip_nodes(tex, tree, c, bump_ch)

            if bump_ch:
                im = tree.nodes.get(c.mr_intensity_multiplier)
                if not im:
                    im = lib.new_intensity_multiplier_node(tree, c, 'mr_intensity_multiplier', bump_ch.mask_bump_value)

                im.inputs[1].default_value = bump_ch.mask_bump_second_edge_value
                if BLENDER_28_GROUP_INPUT_HACK:
                    match_group_input(im, 1)

        if bump_ch:
            im = tree.nodes.get(c.intensity_multiplier)
            if not im:
                im = lib.new_intensity_multiplier_node(tree, c, 'intensity_multiplier', bump_ch.mask_bump_value)

            # Invert other intensity multipler if mask bump flip active
            if bump_ch.mask_bump_flip or tex.type == 'BACKGROUND':
                im.inputs['Invert'].default_value = 1.0
            else: im.inputs['Invert'].default_value = 0.0

            if BLENDER_28_GROUP_INPUT_HACK:
                match_group_input(im, 'Invert')

def check_transition_ao_nodes(tree, tex, ch, bump_ch=None):

    if not bump_ch or tex.type == 'BACKGROUND':
        remove_node(tree, ch, 'tao')

    elif bump_ch != ch and ch.enable_transition_ao:

        tl = ch.id_data.tl
        match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
        root_ch = tl.channels[int(match.group(2))]

        tao = tree.nodes.get(ch.tao)

        # Check if node tree isn't match
        if tao:
            using_flip = tao.node_tree.name.startswith(lib.TRANSITION_AO_FLIP)
            if (
                (using_flip and not bump_ch.mask_bump_flip and tex.type != 'BACKGROUND') or 
                (not using_flip and (bump_ch.mask_bump_flip or tex.type == 'BACKGROUND'))
                ):
                remove_node(tree, ch, 'tao')
                tao = None

        if not tao:
            tao = new_node(tree, ch, 'tao', 'ShaderNodeGroup', 'Transition AO')
            if bump_ch.mask_bump_flip or tex.type == 'BACKGROUND':
                tao.node_tree = lib.get_node_tree_lib(lib.TRANSITION_AO_FLIP)
            else: tao.node_tree = lib.get_node_tree_lib(lib.TRANSITION_AO)

            col = (ch.transition_ao_color.r, ch.transition_ao_color.g, ch.transition_ao_color.b, 1.0)
            tao.inputs['AO Color'].default_value = col

            if bump_ch.mask_bump_flip or tex.type == 'BACKGROUND':
                tao.inputs['Edge'].default_value = -ch.transition_ao_edge
            else: tao.inputs['Edge'].default_value = ch.transition_ao_edge

            tao.inputs['Intensity'].default_value = ch.transition_ao_intensity
            #tao.inputs['Gamma'].default_value = 1.0
            if root_ch.colorspace == 'SRGB':
                tao.inputs['Gamma'].default_value = 1.0/GAMMA
            else: tao.inputs['Gamma'].default_value = 1.0

            if BLENDER_28_GROUP_INPUT_HACK:
                duplicate_lib_node_tree(tao)
                match_group_input(tao)

def set_transition_ramp_nodes(tree, tex, ch, rearrange=False):

    tl = ch.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
    root_ch = tl.channels[int(match.group(2))]

    mr_ramp = tree.nodes.get(ch.mr_ramp)
    mr_linear = tree.nodes.get(ch.mr_linear)
    mr_alpha = tree.nodes.get(ch.mr_alpha)
    mr_intensity = tree.nodes.get(ch.mr_intensity)
    mr_blend = tree.nodes.get(ch.mr_blend)

    if not mr_ramp:
        mr_ramp = new_node(tree, ch, 'mr_ramp', 'ShaderNodeValToRGB', 'Transition Ramp')
        mr_ramp.color_ramp.elements[0].color = (1,1,1,1)
        mr_ramp.color_ramp.elements[1].color = (0.0,0.0,0.0,1)
        rearrange = True

    if not mr_linear:
        mr_linear = new_node(tree, ch, 'mr_linear', 'ShaderNodeGamma', 'Transition Ramp Linear')
        if root_ch.colorspace == 'SRGB':
            mr_linear.inputs[1].default_value = 1.0/GAMMA
        else: mr_linear.inputs[1].default_value = 1.0

    if not mr_alpha:
        mr_alpha = new_node(tree, ch, 'mr_alpha', 'ShaderNodeMath', 'Transition Ramp Alpha')
        mr_alpha.operation = 'MULTIPLY'
        rearrange = True

    if not mr_intensity:
        mr_intensity = new_node(tree, ch, 'mr_intensity', 'ShaderNodeMath', 'Transition Ramp Intensity')
        mr_intensity.operation = 'MULTIPLY'
        mr_intensity.inputs[1].default_value = ch.mask_ramp_intensity_value
        rearrange = True

    if not mr_blend:
        mr_blend = new_node(tree, ch, 'mr_blend', 'ShaderNodeMixRGB', 'Transition Ramp Blend')
        rearrange = True

    mr_blend.blend_type = ch.mask_ramp_blend_type
    mr_blend.mute = not ch.enable
    if len(mr_blend.outputs[0].links) == 0:
        rearrange = True

    return rearrange

def remove_transition_ramp_nodes(tree, ch, clean=False):
    #mute_node(tree, ch, 'mr_blend')
    remove_node(tree, ch, 'mr_linear')
    remove_node(tree, ch, 'mr_inverse')
    remove_node(tree, ch, 'mr_alpha')
    remove_node(tree, ch, 'mr_intensity_multiplier')
    remove_node(tree, ch, 'mr_intensity')
    remove_node(tree, ch, 'mr_blend')

    if clean:
        remove_node(tree, ch, 'mr_ramp')

    # Remove flip bump related nodes
    remove_transition_ramp_flip_nodes(tree, ch)

def check_transition_bump_nodes(tex, tree, ch, ch_index):

    if ch.enable_mask_bump and ch.enable:
        set_transition_bump_nodes(tex, tree, ch, ch_index)
    else: remove_transition_bump_nodes(tex, tree, ch, ch_index)

    # Add intensity multiplier to other channel
    check_transition_bump_influences_to_other_channels(tex, tree)

    # Set mask multiply nodes
    set_mask_multiply_nodes(tex, tree)

    # Check bump base
    check_create_bump_base(tex, tree, ch)
    
    rearrange_tex_nodes(tex)
    reconnect_tex_nodes(tex) #, mod_reconnect=True)

def set_transition_bump_nodes(tex, tree, ch, ch_index):

    tl = tex.id_data.tl

    for i, c in enumerate(tex.channels):
        if tl.channels[i].type == 'NORMAL' and c.enable_mask_bump and c != ch:
            # Disable this mask bump if other channal already use mask bump
            if c.enable:
                tl.halt_update = True
                ch.enable_mask_bump = False
                tl.halt_update = False
                return
            # Disable other mask bump if other channal aren't enabled
            else:
                tl.halt_update = True
                c.enable_mask_bump = False
                tl.halt_update = False

    if ch.mask_bump_type == 'FINE_BUMP_MAP':

        enable_tex_source_tree(tex)
        Modifier.enable_modifiers_tree(ch)

        # Get fine bump
        mb_fine_bump = tree.nodes.get(ch.mb_fine_bump)
        if not mb_fine_bump:
            mb_fine_bump = new_node(tree, ch, 'mb_fine_bump', 'ShaderNodeGroup', 'Transition Fine Bump')
            mb_fine_bump.node_tree = lib.get_node_tree_lib(lib.FINE_BUMP)

            if BLENDER_28_GROUP_INPUT_HACK:
                duplicate_lib_node_tree(mb_fine_bump)

        if ch.mask_bump_flip or tex.type == 'BACKGROUND':
            mb_fine_bump.inputs[0].default_value = -get_transition_fine_bump_distance(ch.mask_bump_distance)
        else: mb_fine_bump.inputs[0].default_value = get_transition_fine_bump_distance(ch.mask_bump_distance)

        if BLENDER_28_GROUP_INPUT_HACK:
            match_group_input(mb_fine_bump, 0)

    else:
        remove_node(tree, ch, 'mb_fine_bump')

    if ch.mask_bump_type == 'CURVED_BUMP_MAP':

        enable_tex_source_tree(tex)
        Modifier.enable_modifiers_tree(ch)

        # Get curved fine bump
        mb_curved_bump = tree.nodes.get(ch.mb_curved_bump)

        if not mb_curved_bump:
            mb_curved_bump = new_node(tree, ch, 'mb_curved_bump', 'ShaderNodeGroup', 'Transition Curved Bump')
        elif BLENDER_28_GROUP_INPUT_HACK and mb_curved_bump.node_tree:
            # Remove prev tree
            bpy.data.node_groups.remove(mb_curved_bump.node_tree)

        if ch.mask_bump_flip or tex.type == 'BACKGROUND':
            mb_curved_bump.node_tree = lib.get_node_tree_lib(lib.FLIP_CURVED_FINE_BUMP)
        else:
            mb_curved_bump.node_tree = lib.get_node_tree_lib(lib.CURVED_FINE_BUMP)

        if BLENDER_28_GROUP_INPUT_HACK:
            duplicate_lib_node_tree(mb_curved_bump)

        if ch.mask_bump_flip or tex.type == 'BACKGROUND':
            mb_curved_bump.inputs[0].default_value = -get_transition_fine_bump_distance(ch.mask_bump_distance, True)
        else: mb_curved_bump.inputs[0].default_value = get_transition_fine_bump_distance(ch.mask_bump_distance, True)

        mb_curved_bump.inputs['Offset'].default_value = ch.mask_bump_curved_offset

        if BLENDER_28_GROUP_INPUT_HACK:
            match_group_input(mb_curved_bump, 0)
            match_group_input(mb_curved_bump, 'Offset')

    else:
        remove_node(tree, ch, 'mb_curved_bump')

    if ch.mask_bump_type == 'BUMP_MAP':

        disable_tex_source_tree(tex, False)
        Modifier.disable_modifiers_tree(ch)

        # Get bump
        mb_bump = tree.nodes.get(ch.mb_bump)
        if not mb_bump:
            mb_bump = new_node(tree, ch, 'mb_bump', 'ShaderNodeBump', 'Transition Bump')

        if ch.mask_bump_flip or tex.type == 'BACKGROUND':
            mb_bump.inputs[1].default_value = -ch.mask_bump_distance
        else: mb_bump.inputs[1].default_value = ch.mask_bump_distance

    else:
        remove_node(tree, ch, 'mb_bump')

    # Add inverse
    mb_inverse = tree.nodes.get(ch.mb_inverse)
    if not mb_inverse:
        mb_inverse = new_node(tree, ch, 'mb_inverse', 'ShaderNodeMath', 'Transition Bump Inverse')
        mb_inverse.operation = 'SUBTRACT'
        mb_inverse.inputs[0].default_value = 1.0

    mb_intensity_multiplier = tree.nodes.get(ch.mb_intensity_multiplier)
    if not mb_intensity_multiplier:
        mb_intensity_multiplier = lib.new_intensity_multiplier_node(tree, ch, 
                'mb_intensity_multiplier', ch.mask_bump_value)

    intensity_multiplier = tree.nodes.get(ch.intensity_multiplier)
    if not intensity_multiplier:
        intensity_multiplier = lib.new_intensity_multiplier_node(tree, ch, 
                'intensity_multiplier', ch.mask_bump_value)

    if ch.mask_bump_flip or tex.type == 'BACKGROUND':
        intensity_multiplier.inputs[1].default_value = ch.mask_bump_second_edge_value
        mb_intensity_multiplier.inputs[1].default_value = ch.mask_bump_value
        intensity_multiplier.inputs['Sharpen'].default_value = 0.0
        mb_intensity_multiplier.inputs['Sharpen'].default_value = 1.0
    else:
        intensity_multiplier.inputs[1].default_value = ch.mask_bump_value
        mb_intensity_multiplier.inputs[1].default_value = ch.mask_bump_second_edge_value
        intensity_multiplier.inputs['Sharpen'].default_value = 1.0
        mb_intensity_multiplier.inputs['Sharpen'].default_value = 0.0

    if BLENDER_28_GROUP_INPUT_HACK:
        match_group_input(mb_intensity_multiplier)
        match_group_input(intensity_multiplier)

    # Add vector mix
    mb_blend = tree.nodes.get(ch.mb_blend)
    if not mb_blend:
        mb_blend = new_node(tree, ch, 'mb_blend', 'ShaderNodeGroup', 'Transition Vector Blend')
        mb_blend.node_tree = lib.get_node_tree_lib(lib.VECTOR_MIX)

    # Dealing with mask sources
    check_transition_bump_source_tree(tex, ch)

def remove_transition_bump_influence_nodes_to_other_channels(tex, tree):
    # Delete intensity multiplier from ramp
    for c in tex.channels:
        remove_node(tree, c, 'intensity_multiplier')
        remove_node(tree, c, 'mr_intensity_multiplier')

        # Ramp intensity value should only use its own value if bump aren't available
        if c.enable_mask_ramp:
            mr_intensity = tree.nodes.get(c.mr_intensity)
            if mr_intensity:
                mr_intensity.inputs[1].default_value = c.mask_ramp_intensity_value

            # Remove flip bump related nodes
            check_transition_ramp_flip_nodes(tex, tree, c)

        # Remove transition ao related nodes
        check_transition_ao_nodes(tree, tex, c)

def remove_transition_bump_nodes(tex, tree, ch, ch_index):

    disable_tex_source_tree(tex, False)
    Modifier.disable_modifiers_tree(ch)

    remove_node(tree, ch, 'intensity_multiplier')
    remove_node(tree, ch, 'mb_bump')
    remove_node(tree, ch, 'mb_fine_bump')
    remove_node(tree, ch, 'mb_curved_bump')
    remove_node(tree, ch, 'mb_inverse')
    remove_node(tree, ch, 'mb_intensity_multiplier')
    remove_node(tree, ch, 'mb_blend')

    for mask in tex.masks:
        disable_mask_source_tree(tex, mask, False)

        c = mask.channels[ch_index]
        remove_node(tree, c, 'multiply_n')
        remove_node(tree, c, 'multiply_s')
        remove_node(tree, c, 'multiply_e')
        remove_node(tree, c, 'multiply_w')

    remove_transition_bump_influence_nodes_to_other_channels(tex, tree)

def check_transition_bump_source_tree(tex, bump_ch):

    chain = min(bump_ch.mask_bump_chain, len(tex.masks))

    for i, mask in enumerate(tex.masks):

        if bump_ch.mask_bump_type in {'FINE_BUMP_MAP', 'CURVED_BUMP_MAP'} and i < chain:
            enable_mask_source_tree(tex, mask)
        else:
            disable_mask_source_tree(tex, mask)

def update_transition_ramp_intensity_value(self, context):
    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    tree = get_tree(tex)

    mr_intensity = tree.nodes.get(self.mr_intensity)
    if mr_intensity: 
        flip_bump = any([c for c in tex.channels if (
            c.mask_bump_flip or tex.type=='BACKGROUND') and c.enable_mask_bump])

        if flip_bump:
            mr_intensity.inputs[1].default_value = self.mask_ramp_intensity_value * self.intensity_value
        else: mr_intensity.inputs[1].default_value = self.mask_ramp_intensity_value

def update_transition_ramp_blend_type(self, context):
    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    tree = get_tree(tex)

    mr_blend = tree.nodes.get(self.mr_blend)
    mr_blend.blend_type = self.mask_ramp_blend_type

def update_transition_bump_value(self, context):
    if not self.enable: return

    tl = self.id_data.tl
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    tree = get_tree(tex)
    ch = self

    mb_intensity_multiplier = tree.nodes.get(ch.mb_intensity_multiplier)
    intensity_multiplier = tree.nodes.get(ch.intensity_multiplier)

    if ch.mask_bump_flip or tex.type=='BACKGROUND':
        if intensity_multiplier:
            intensity_multiplier.inputs[1].default_value = ch.mask_bump_second_edge_value
        if mb_intensity_multiplier:
            mb_intensity_multiplier.inputs[1].default_value = ch.mask_bump_value
    else:
        if intensity_multiplier:
            intensity_multiplier.inputs[1].default_value = ch.mask_bump_value
        if mb_intensity_multiplier:
            mb_intensity_multiplier.inputs[1].default_value = ch.mask_bump_second_edge_value

    if BLENDER_28_GROUP_INPUT_HACK:
        match_group_input(mb_intensity_multiplier, 1)

    for c in tex.channels:
        if c == ch: continue

        im = tree.nodes.get(c.mr_intensity_multiplier)
        if im:
            im.inputs[1].default_value = ch.mask_bump_second_edge_value

            if BLENDER_28_GROUP_INPUT_HACK:
                match_group_input(im, 1)

        im = tree.nodes.get(c.intensity_multiplier)
        if im: 
            im.inputs[1].default_value = ch.mask_bump_value

            if BLENDER_28_GROUP_INPUT_HACK:
                match_group_input(im, 1)

def update_transition_bump_distance(self, context):
    if not self.enable: return

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch_index = int(match.group(2))
    ch = self
    tree = get_tree(tex)

    if ch.mask_bump_type == 'CURVED_BUMP_MAP':
        mb_curved_bump = tree.nodes.get(ch.mb_curved_bump)
        if mb_curved_bump:
            if ch.mask_bump_flip or tex.type=='BACKGROUND':
                mb_curved_bump.inputs[0].default_value = -get_transition_fine_bump_distance(ch.mask_bump_distance, True)
            else: mb_curved_bump.inputs[0].default_value = get_transition_fine_bump_distance(ch.mask_bump_distance, True)

            if BLENDER_28_GROUP_INPUT_HACK:
                match_group_input(mb_curved_bump, 0)

    elif ch.mask_bump_type == 'FINE_BUMP_MAP':
        mb_fine_bump = tree.nodes.get(ch.mb_fine_bump)
        if mb_fine_bump:
            if ch.mask_bump_flip or tex.type=='BACKGROUND':
                mb_fine_bump.inputs[0].default_value = -get_transition_fine_bump_distance(ch.mask_bump_distance)
            else: mb_fine_bump.inputs[0].default_value = get_transition_fine_bump_distance(ch.mask_bump_distance)

            if BLENDER_28_GROUP_INPUT_HACK:
                match_group_input(mb_fine_bump, 0)

    elif ch.mask_bump_type == 'BUMP_MAP':
        mb_bump = tree.nodes.get(ch.mb_bump)
        if mb_bump:
            if ch.mask_bump_flip or tex.type=='BACKGROUND':
                mb_bump.inputs[1].default_value = -ch.mask_bump_distance
            else: mb_bump.inputs[1].default_value = ch.mask_bump_distance

def update_transition_bump_chain(self, context):
    T = time.time()

    tl = self.id_data.tl
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    tree = get_tree(tex)
    ch = self

    if ch.enable_mask_bump and ch.enable:

        set_mask_multiply_nodes(tex, tree, ch)
        check_transition_bump_source_tree(tex, ch)

        rearrange_tex_nodes(tex)
        reconnect_tex_nodes(tex) #, mod_reconnect=True)

        print('INFO: Transition bump chain is updated at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def update_transition_bump_curved_offset(self, context):

    tl = self.id_data.tl
    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(m.group(1))]
    tree = get_tree(tex)
    ch = self

    mb_curved_bump = tree.nodes.get(ch.mb_curved_bump)
    if mb_curved_bump:
        mb_curved_bump.inputs['Offset'].default_value = ch.mask_bump_curved_offset

def update_transition_ao_intensity(self, context):

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch = self
    tree = get_tree(tex)

    tao = tree.nodes.get(ch.tao)
    if tao:
        tao.inputs['Intensity'].default_value = ch.transition_ao_intensity

def update_transition_ao_edge(self, context):

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch = self
    tree = get_tree(tex)

    bump_ch = get_transition_bump_channel(tex)

    tao = tree.nodes.get(ch.tao)
    if tao and bump_ch:
        if bump_ch.mask_bump_flip or tex.type=='BACKGROUND':
            tao.inputs['Edge'].default_value = -ch.transition_ao_edge
        else: tao.inputs['Edge'].default_value = ch.transition_ao_edge

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

def update_enable_transition_ao(self, context):

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch = self

    tree = get_tree(tex)

    # Get transition bump
    bump_ch = get_transition_bump_channel(tex)

    check_transition_ao_nodes(tree, tex, ch, bump_ch)

    # Update mask multiply
    set_mask_multiply_nodes(tex, tree)

    rearrange_tex_nodes(tex)
    reconnect_tex_nodes(tex)

def update_enable_transition_ramp(self, context):
    T = time.time()

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    ch = self

    tree = get_tree(tex)

    if self.enable_mask_ramp:
        set_transition_ramp_nodes(tree, tex, ch)
    else: remove_transition_ramp_nodes(tree, ch)

    # Check nodes related to transition bump
    check_transition_bump_influences_to_other_channels(tex, tree, target_ch=ch)

    # Update mask multiply
    set_mask_multiply_nodes(tex, tree)

    rearrange_tex_nodes(tex)
    reconnect_tex_nodes(tex)

    if ch.enable_mask_ramp:
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

    if ch.enable_mask_bump:
        print('INFO: Transition bump is enabled at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')
    else: print('INFO: Transition bump is disabled at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def register():
    pass

def unregister():
    pass
