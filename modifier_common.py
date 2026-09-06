import bpy, re
from .common import *
from .subtree import *
from .node_connections import *
from .node_arrangements import *
from . import lib

modifier_type_items = (
    ('INVERT', 'Invert', 'Invert input RGB and/or Alpha', 'MODIFIER', 0),

    (
        'RGB_TO_INTENSITY', 'RGB to Alpha',
        'Input RGB will be used as alpha output, Output RGB will be replaced using custom color.', 
        'MODIFIER', 1
    ),

    (
        'INTENSITY_TO_RGB', 'Alpha to RGB',
        'Input alpha will be used as RGB output, Output Alpha will use solid value of one.', 
        'MODIFIER', 2
    ),

    # Deprecated
    (
        'OVERRIDE_COLOR', 'Override Color',
        'Input RGB will be replaced with custom RGB', 
        'MODIFIER', 3
    ),

    ('COLOR_RAMP', 'Color Ramp', '', 'MODIFIER', 4),
    ('RGB_CURVE', 'RGB Curve', '', 'MODIFIER', 5),
    ('HUE_SATURATION', 'Hue Saturation', '', 'MODIFIER', 6),
    ('BRIGHT_CONTRAST', 'Brightness Contrast', '', 'MODIFIER', 7),
    # Deprecated
    ('MULTIPLIER', 'Multiplier', '', 'MODIFIER', 8),
    ('MATH', 'Math', '', 'MODIFIER',9)
)

def get_modifier_channel_type(mod, return_non_color=False):

    yp = mod.id_data.yp
    match1 = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())
    match2 = re.match(r'yp\.channels\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())
    match3 = re.match(r'yp\.layers\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())
    if match1: 
        root_ch = yp.channels[int(match1.group(2))]

        # Get non color flag and channel type
        non_color = root_ch.colorspace == 'LINEAR'
        channel_type = root_ch.type
    elif match2:
        root_ch = yp.channels[int(match2.group(1))]

        # Get non color flag and channel type
        non_color = root_ch.colorspace == 'LINEAR'
        channel_type = root_ch.type
    elif match3:

        # Image layer modifiers always use srgb colorspace
        layer = yp.layers[int(match3.group(1))]
        non_color = layer.type != 'IMAGE'
        channel_type = 'RGB'

    if return_non_color:
        return channel_type, non_color

    return channel_type

def save_rgb2i_props(tree, m):
    rgb2i = tree.nodes.get(m.rgb2i)
    root_tree = m.id_data
    if rgb2i:

        for fcs in get_action_and_driver_fcurves(tree):
            for fc in fcs:
                match = re.match(r'^nodes\["' + m.rgb2i + r'"\]\.inputs\[(\d+)\]\.default_value$', fc.data_path)
                if match:
                    index = int(match.group(1))
                    if index == 3:
                        if root_tree != tree: copy_fcurves(fc, root_tree, m, 'rgb2i_col')
                        else: fc.data_path = m.path_from_id() + '.rgb2i_col'

        m.rgb2i_col = rgb2i.inputs['RGB To Intensity Color'].default_value

def load_rgb2i_anim_props(tree, m):
    rgb2i = tree.nodes.get(m.rgb2i)
    root_tree = m.id_data
    if rgb2i:
        for fcs in get_action_and_driver_fcurves(root_tree):
            for fc in reversed(fcs):
                if root_tree != tree:
                    # Copy fcurve if the tree is different
                    if fc.data_path == m.path_from_id() + '.rgb2i_col': 
                        copy_fcurves(fc, tree, rgb2i.inputs[3], 'default_value')
                        fcs.remove(fc)
                else:
                    # Rename data path if the tree is the same
                    if fc.data_path == m.path_from_id() + '.rgb2i_col': fc.data_path = 'nodes["' + m.rgb2i + '"].inputs[3].default_value'

def save_huesat_props(tree, m):
    huesat = tree.nodes.get(m.huesat)
    root_tree = m.id_data
    if huesat:

        for fcs in get_action_and_driver_fcurves(tree):
            for fc in fcs:
                match = re.match(r'^nodes\["' + m.huesat + r'"\]\.inputs\[(\d+)\]\.default_value$', fc.data_path)
                if match:
                    index = int(match.group(1))
                    if root_tree != tree:
                        # Copy fcurve to yp attributes if the tree is different
                        if index == 0: copy_fcurves(fc, root_tree, m, 'huesat_hue_val')
                        elif index == 1: copy_fcurves(fc, root_tree, m, 'huesat_saturation_val')
                        elif index == 2: copy_fcurves(fc, root_tree, m, 'huesat_value_val')
                    else:
                        # Rename data path if the tree is the same
                        if index == 0: fc.data_path = m.path_from_id() + '.huesat_hue_val'
                        elif index == 1: fc.data_path = m.path_from_id() + '.huesat_saturation_val'
                        elif index == 2: fc.data_path = m.path_from_id() + '.huesat_value_val'

        m.huesat_hue_val = huesat.inputs['Hue'].default_value
        m.huesat_saturation_val = huesat.inputs['Saturation'].default_value
        m.huesat_value_val = huesat.inputs['Value'].default_value

def load_huesat_anim_props(tree, m):
    huesat = tree.nodes.get(m.huesat)
    root_tree = m.id_data
    if huesat:

        for fcs in get_action_and_driver_fcurves(root_tree):
            for fc in reversed(fcs):
                if root_tree != tree:
                    # Copy fcurve if the tree is different
                    if fc.data_path == m.path_from_id() + '.huesat_hue_val': 
                        copy_fcurves(fc, tree, huesat.inputs[0], 'default_value')
                        fcs.remove(fc)
                    elif fc.data_path == m.path_from_id() + '.huesat_saturation_val': 
                        copy_fcurves(fc, tree, huesat.inputs[1], 'default_value')
                        fcs.remove(fc)
                    elif fc.data_path == m.path_from_id() + '.huesat_value_val': 
                        copy_fcurves(fc, tree, huesat.inputs[2], 'default_value')
                        fcs.remove(fc)
                else:
                    # Rename data path if the tree is the same
                    if fc.data_path == m.path_from_id() + '.huesat_hue_val': fc.data_path = 'nodes["' + m.huesat + '"].inputs[0].default_value'
                    elif fc.data_path == m.path_from_id() + '.huesat_saturation_val': fc.data_path = 'nodes["' + m.huesat + '"].inputs[1].default_value'
                    elif fc.data_path == m.path_from_id() + '.huesat_value_val': fc.data_path = 'nodes["' + m.huesat + '"].inputs[2].default_value'

def save_brightcon_props(tree, m):
    brightcon = tree.nodes.get(m.brightcon)
    root_tree = m.id_data
    if brightcon:

        for fcs in get_action_and_driver_fcurves(tree):
            for fc in fcs:
                match = re.match(r'^nodes\["' + m.brightcon + r'"\]\.inputs\[(\d+)\]\.default_value$', fc.data_path)
                if match:
                    index = int(match.group(1))
                    if root_tree != tree:
                        # Copy fcurve to yp attributes if the tree is different
                        if index == 1: copy_fcurves(fc, root_tree, m, 'brightness_value')
                        elif index == 2: copy_fcurves(fc, root_tree, m, 'contrast_value')
                    else:
                        # Rename data path if the tree is the same
                        if index == 1: fc.data_path = m.path_from_id() + '.brightness_value'
                        elif index == 2: fc.data_path = m.path_from_id() + '.contrast_value'

        m.brightness_value = brightcon.inputs['Bright'].default_value
        m.contrast_value = brightcon.inputs['Contrast'].default_value

def load_brightcon_anim_props(tree, m):
    brightcon = tree.nodes.get(m.brightcon)
    root_tree = m.id_data
    if brightcon:

        for fcs in get_action_and_driver_fcurves(root_tree):
            for fc in reversed(fcs):
                if root_tree != tree:
                    # Copy fcurve if the tree is different
                    if fc.data_path == m.path_from_id() + '.brightness_value': 
                        copy_fcurves(fc, tree, brightcon.inputs[1], 'default_value')
                        fcs.remove(fc)
                    elif fc.data_path == m.path_from_id() + '.contrast_value': 
                        copy_fcurves(fc, tree, brightcon.inputs[2], 'default_value')
                        fcs.remove(fc)
                else:
                    # Rename data path if the tree is the same
                    if fc.data_path == m.path_from_id() + '.brightness_value': fc.data_path = 'nodes["' + m.brightcon + '"].inputs[1].default_value'
                    elif fc.data_path == m.path_from_id() + '.contrast_value': fc.data_path = 'nodes["' + m.brightcon + '"].inputs[2].default_value'

def save_math_props(tree, m, channel_type):
    math = tree.nodes.get(m.math)
    root_tree = m.id_data
    if math:

        for fcs in get_action_and_driver_fcurves(tree):
            for fc in fcs:
                match = re.match(r'^nodes\["' + m.math + r'"\]\.inputs\[(\d+)\]\.default_value$', fc.data_path)
                if match:
                    index = int(match.group(1))
                    if root_tree != tree:
                        # Copy fcurve to yp attributes if the tree is different
                        if channel_type == 'VALUE':
                            if index == 2: copy_fcurves(fc, root_tree, m, 'math_r_val')
                            elif index == 3: copy_fcurves(fc, root_tree, m, 'math_a_val')
                        else:
                            if index == 2: copy_fcurves(fc, root_tree, m, 'math_r_val')
                            elif index == 3: copy_fcurves(fc, root_tree, m, 'math_g_val')
                            elif index == 4: copy_fcurves(fc, root_tree, m, 'math_b_val')
                            elif index == 5: copy_fcurves(fc, root_tree, m, 'math_a_val')
                    else:
                        # Rename data path if the tree is the same
                        if channel_type == 'VALUE':
                            if index == 2: fc.data_path = m.path_from_id() + '.math_r_val'
                            elif index == 3: fc.data_path = m.path_from_id() + '.math_a_val'
                        else:
                            if index == 2: fc.data_path = m.path_from_id() + '.math_r_val'
                            elif index == 3: fc.data_path = m.path_from_id() + '.math_g_val'
                            elif index == 4: fc.data_path = m.path_from_id() + '.math_b_val'
                            elif index == 5: fc.data_path = m.path_from_id() + '.math_a_val'

        m.math_r_val = math.inputs[2].default_value
        if channel_type == 'VALUE':
            m.math_a_val = math.inputs[3].default_value
        else:
            m.math_g_val = math.inputs[3].default_value
            m.math_b_val = math.inputs[4].default_value
            m.math_a_val = math.inputs[5].default_value

def load_math_anim_props(tree, m, channel_type):
    math = tree.nodes.get(m.math)
    root_tree = m.id_data
    if math:

        for fcs in get_action_and_driver_fcurves(root_tree):
            for fc in reversed(fcs):
                if root_tree != tree:
                    # Copy fcurve if the tree is different
                    if channel_type == 'VALUE':
                        if fc.data_path == m.path_from_id() + '.math_r_val': 
                            copy_fcurves(fc, tree, math.inputs[2], 'default_value')
                            fcs.remove(fc)
                        elif fc.data_path == m.path_from_id() + '.math_a_val': 
                            copy_fcurves(fc, tree, math.inputs[3], 'default_value')
                            fcs.remove(fc)
                    else:
                        if fc.data_path == m.path_from_id() + '.math_r_val': 
                            copy_fcurves(fc, tree, math.inputs[2], 'default_value')
                            fcs.remove(fc)
                        elif fc.data_path == m.path_from_id() + '.math_g_val': 
                            copy_fcurves(fc, tree, math.inputs[3], 'default_value')
                            fcs.remove(fc)
                        elif fc.data_path == m.path_from_id() + '.math_b_val': 
                            copy_fcurves(fc, tree, math.inputs[4], 'default_value')
                            fcs.remove(fc)
                        elif fc.data_path == m.path_from_id() + '.math_a_val': 
                            copy_fcurves(fc, tree, math.inputs[5], 'default_value')
                            fcs.remove(fc)
                else:
                    # Rename data path if the tree is the same
                    if channel_type == 'VALUE':
                        if fc.data_path == m.path_from_id() + '.math_r_val': fc.data_path = 'nodes["' + m.math + '"].inputs[2].default_value'
                        elif fc.data_path == m.path_from_id() + '.math_a_val': fc.data_path = 'nodes["' + m.math + '"].inputs[3].default_value'
                    else:
                        if fc.data_path == m.path_from_id() + '.math_r_val': fc.data_path = 'nodes["' + m.math + '"].inputs[2].default_value'
                        elif fc.data_path == m.path_from_id() + '.math_g_val': fc.data_path = 'nodes["' + m.math + '"].inputs[3].default_value'
                        elif fc.data_path == m.path_from_id() + '.math_b_val': fc.data_path = 'nodes["' + m.math + '"].inputs[4].default_value'
                        elif fc.data_path == m.path_from_id() + '.math_a_val': fc.data_path = 'nodes["' + m.math + '"].inputs[5].default_value'

def check_modifier_nodes(m, tree, ref_tree=None):

    yp = m.id_data.yp
    nodes = tree.nodes

    # Get channel type and non color status
    channel_type, non_color = get_modifier_channel_type(m, True)
    used_by_paired_alpha = is_modifier_used_by_paired_alpha_channel(m)

    # Check the nodes
    if m.type == 'INVERT':

        if not m.enable:
            remove_node(tree, m, 'invert')
        else:
            if ref_tree:
                invert_ref = ref_tree.nodes.get(m.invert)
                if invert_ref: ref_tree.nodes.remove(invert_ref)

                invert = new_node(tree, m, 'invert', 'ShaderNodeGroup', 'Invert')
                dirty = True
            else:
                invert, dirty = check_new_node(tree, m, 'invert', 'ShaderNodeGroup', 'Invert', True)

            if dirty:
                if channel_type == 'VALUE':
                    invert.node_tree = get_node_tree_lib(lib.MOD_INVERT_VALUE)
                else: invert.node_tree = get_node_tree_lib(lib.MOD_INVERT)

                invert.inputs[2].default_value = 1.0 if m.invert_r_enable else 0.0
                if channel_type == 'VALUE':
                    invert.inputs[3].default_value = 1.0 if m.invert_a_enable else 0.0
                else:
                    invert.inputs[3].default_value = 1.0 if m.invert_g_enable else 0.0
                    invert.inputs[4].default_value = 1.0 if m.invert_b_enable else 0.0
                    invert.inputs[5].default_value = 1.0 if m.invert_a_enable else 0.0

    elif m.type == 'RGB_TO_INTENSITY':

        if not m.enable:
            save_rgb2i_props(tree, m)
            remove_node(tree, m, 'rgb2i')
        else:
            if ref_tree:
                save_rgb2i_props(tree, m)
                rgb2i_ref = ref_tree.nodes.get(m.rgb2i)
                if rgb2i_ref: ref_tree.nodes.remove(rgb2i_ref)

                rgb2i = new_node(tree, m, 'rgb2i', 'ShaderNodeGroup', 'RGB to Intensity')
                dirty = True
            else:
                rgb2i, dirty = check_new_node(tree, m, 'rgb2i', 'ShaderNodeGroup', 'RGB to Intensity', True)

            if dirty:
                rgb2i.node_tree = get_node_tree_lib(lib.MOD_RGB2INT)

                rgb2i.inputs['RGB To Intensity Color'].default_value = m.rgb2i_col
                if non_color:
                    rgb2i.inputs['Gamma'].default_value = 1.0
                else: rgb2i.inputs['Gamma'].default_value = 1.0 / GAMMA

                load_rgb2i_anim_props(tree, m)

    elif m.type == 'INTENSITY_TO_RGB':

        if not m.enable:
            remove_node(tree, m, 'i2rgb')
        else:
            if ref_tree:
                i2rgb_ref = ref_tree.nodes.get(m.i2rgb)
                if i2rgb_ref: ref_tree.nodes.remove(i2rgb_ref)

                i2rgb = new_node(tree, m, 'i2rgb', 'ShaderNodeGroup', 'Intensity to RGB')
                dirty = True
            else:
                i2rgb, dirty = check_new_node(tree, m, 'i2rgb', 'ShaderNodeGroup', 'Intensity to RGB', True)

            if dirty:
                i2rgb.node_tree = get_node_tree_lib(lib.MOD_INT2RGB)

    elif m.type == 'OVERRIDE_COLOR':

        if not m.enable:
            remove_node(tree, m, 'oc')
        else:
            if ref_tree:
                oc_ref = ref_tree.nodes.get(m.oc)
                if oc_ref: ref_tree.nodes.remove(oc_ref)

                oc = new_node(tree, m, 'oc', 'ShaderNodeGroup', 'Override Color')
                dirty = True
            else:
                oc, dirty = check_new_node(tree, m, 'oc', 'ShaderNodeGroup', 'Override Color', True)

            if dirty:
                oc.node_tree = get_node_tree_lib(lib.MOD_OVERRIDE_COLOR)

                if channel_type == 'VALUE':
                    col = (m.oc_val, m.oc_val, m.oc_val, 1.0)
                else: col = m.oc_col
                oc.inputs['Override Color'].default_value = col

                if non_color:
                    oc.inputs['Gamma'].default_value = 1.0
                else: oc.inputs['Gamma'].default_value = 1.0 / GAMMA

    elif m.type == 'COLOR_RAMP':

        if not m.enable:

            if ref_tree:
                color_ramp = new_node(tree, m, 'color_ramp', 'ShaderNodeValToRGB', 'ColorRamp')
                color_ramp_ref = ref_tree.nodes.get(m.color_ramp)
                if color_ramp_ref:
                    copy_node_props(color_ramp_ref, color_ramp)
                    ref_tree.nodes.remove(color_ramp_ref)

                # Remove deprecated nodes
                remove_node(ref_tree, m, 'color_ramp_mix_rgb') # Deprecated
                remove_node(ref_tree, m, 'color_ramp_mix_alpha') # Deprecated

            remove_node(tree, m, 'color_ramp_linear_start')
            remove_node(tree, m, 'color_ramp_linear')
            remove_node(tree, m, 'color_ramp_alpha_multiply')

            # Remove deprecated nodes
            remove_node(tree, m, 'color_ramp_mix_rgb') # Deprecated
            remove_node(tree, m, 'color_ramp_mix_alpha') # Deprecated
        else:

            color_ramp_alpha_multiply = None

            if ref_tree:
                color_ramp_alpha_multiply_ref = ref_tree.nodes.get(m.color_ramp_alpha_multiply)
                color_ramp_linear_start_ref = ref_tree.nodes.get(m.color_ramp_linear_start)
                color_ramp_ref = ref_tree.nodes.get(m.color_ramp)
                color_ramp_linear_ref = ref_tree.nodes.get(m.color_ramp_linear)

                # Create new nodes if reference is used
                if m.affect_alpha and m.affect_color and not used_by_paired_alpha:
                    color_ramp_alpha_multiply = new_mix_node(tree, m, 'color_ramp_alpha_multiply', 'ColorRamp Alpha Multiply')

                color_ramp_linear_start = new_node(tree, m, 'color_ramp_linear_start', 'ShaderNodeGamma', 'ColorRamp Linear Start')
                color_ramp = new_node(tree, m, 'color_ramp', 'ShaderNodeValToRGB', 'ColorRamp')
                color_ramp_linear = new_node(tree, m, 'color_ramp_linear', 'ShaderNodeGamma', 'ColorRamp Linear')
                dirty = True
                ramp_dirty = False
            else:

                dirty = False
                if m.affect_alpha and m.affect_color:
                    color_ramp_alpha_multiply, dirty = check_new_mix_node(tree, m, 'color_ramp_alpha_multiply', 'ColorRamp Alpha Multiply', True)

                color_ramp_linear_start = check_new_node(tree, m, 'color_ramp_linear_start', 'ShaderNodeGamma', 'ColorRamp Linear Start')
                color_ramp, ramp_dirty = check_new_node(tree, m, 'color_ramp', 'ShaderNodeValToRGB', 'ColorRamp', True)
                color_ramp_linear = check_new_node(tree, m, 'color_ramp_linear', 'ShaderNodeGamma', 'ColorRamp Linear')

            if ref_tree:

                if color_ramp_alpha_multiply_ref:
                    if color_ramp_alpha_multiply:
                        copy_node_props(color_ramp_alpha_multiply_ref, color_ramp_alpha_multiply)
                    ref_tree.nodes.remove(color_ramp_alpha_multiply_ref)

                if color_ramp_linear_start_ref: 
                    copy_node_props(color_ramp_linear_start_ref, color_ramp_linear_start)
                    ref_tree.nodes.remove(color_ramp_linear_start_ref)

                if color_ramp_ref:
                    copy_node_props(color_ramp_ref, color_ramp)
                    ref_tree.nodes.remove(color_ramp_ref)

                if color_ramp_linear_ref:
                    copy_node_props(color_ramp_linear_ref, color_ramp_linear)
                    ref_tree.nodes.remove(color_ramp_linear_ref)

            if dirty:

                if color_ramp_alpha_multiply:
                    color_ramp_alpha_multiply.inputs[0].default_value = 1.0
                    color_ramp_alpha_multiply.blend_type = 'MULTIPLY'

            if not m.affect_alpha or not m.affect_color or used_by_paired_alpha:
                remove_node(tree, m, 'color_ramp_alpha_multiply')

            if non_color or yp.use_linear_blending:
                remove_node(tree, m, 'color_ramp_linear_start')
                remove_node(tree, m, 'color_ramp_linear')
            else: 
                color_ramp_linear_start.inputs[1].default_value = GAMMA
                color_ramp_linear.inputs[1].default_value = 1.0 / GAMMA

            if ramp_dirty:
                # Set default color if ramp just created
                color_ramp.color_ramp.elements[0].color = (0, 0, 0, 0) 

    elif m.type == 'RGB_CURVE':

        if ref_tree:
            rgb_curve_ref = ref_tree.nodes.get(m.rgb_curve)
            rgb_curve = new_node(tree, m, 'rgb_curve', 'ShaderNodeRGBCurve', 'RGB Curve')
            if rgb_curve_ref:
                # Copy from reference
                copy_node_props(rgb_curve_ref, rgb_curve)
                ref_tree.nodes.remove(rgb_curve_ref)
        else:
            rgb_curve = check_new_node(tree, m, 'rgb_curve', 'ShaderNodeRGBCurve', 'RGB Curve')

    elif m.type == 'HUE_SATURATION':

        if not m.enable:
            save_huesat_props(tree, m)
            remove_node(tree, m, 'huesat')
        else:
            if ref_tree:
                save_huesat_props(tree, m)

                # Remove previous nodes
                huesat_ref = ref_tree.nodes.get(m.huesat)
                if huesat_ref: ref_tree.nodes.remove(huesat_ref)

                huesat = new_node(tree, m, 'huesat', 'ShaderNodeHueSaturation', 'Hue Saturation')
                dirty = True
            else:
                huesat, dirty = check_new_node(tree, m, 'huesat', 'ShaderNodeHueSaturation', 'Hue Saturation', True)

            if dirty:
                huesat.inputs['Hue'].default_value = m.huesat_hue_val
                huesat.inputs['Saturation'].default_value = m.huesat_saturation_val
                huesat.inputs['Value'].default_value = m.huesat_value_val

                load_huesat_anim_props(tree, m)

    elif m.type == 'BRIGHT_CONTRAST':

        if not m.enable:
            save_brightcon_props(tree, m)
            remove_node(tree, m, 'brightcon')
        else:
            if ref_tree:
                save_brightcon_props(tree, m)

                # Remove previous nodes
                brightcon_ref = ref_tree.nodes.get(m.brightcon)
                if brightcon_ref: ref_tree.nodes.remove(brightcon_ref)

                brightcon = new_node(tree, m, 'brightcon', 'ShaderNodeBrightContrast', 'Brightness Contrast')
                dirty = True
            else:
                brightcon, dirty = check_new_node(tree, m, 'brightcon', 'ShaderNodeBrightContrast', 'Brightness Contrast', True)

            if dirty:
                brightcon.inputs['Bright'].default_value = m.brightness_value
                brightcon.inputs['Contrast'].default_value = m.contrast_value

                load_brightcon_anim_props(tree, m)

    elif m.type == 'MULTIPLIER':

        if not m.enable:
            remove_node(tree, m, 'multiplier')
        else:
            if ref_tree:
                # Remove previous nodes
                multiplier_ref = ref_tree.nodes.get(m.multiplier)
                if multiplier_ref: ref_tree.nodes.remove(multiplier_ref)

                multiplier = new_node(tree, m, 'multiplier', 'ShaderNodeGroup', 'Multiplier')
                dirty = True
            else:
                multiplier, dirty = check_new_node(tree, m, 'multiplier', 'ShaderNodeGroup', 'Multiplier', True)

            if dirty:
                if channel_type == 'VALUE':
                    multiplier.node_tree = get_node_tree_lib(lib.MOD_MULTIPLIER_VALUE)
                else: multiplier.node_tree = get_node_tree_lib(lib.MOD_MULTIPLIER)

                multiplier.inputs[2].default_value = 1.0 if m.use_clamp else 0.0
                multiplier.inputs[3].default_value = m.multiplier_r_val
                if channel_type == 'VALUE':
                    multiplier.inputs[4].default_value = m.multiplier_a_val
                else:
                    multiplier.inputs[4].default_value = m.multiplier_g_val
                    multiplier.inputs[5].default_value = m.multiplier_b_val
                    multiplier.inputs[6].default_value = m.multiplier_a_val

    elif m.type == 'MATH':

        if not m.enable:
            save_math_props(tree, m, channel_type)
            remove_node(tree, m, 'math')
        else:
            if ref_tree:
                save_math_props(ref_tree, m, channel_type)

                # Remove previous nodes
                math_ref = ref_tree.nodes.get(m.math)
                if math_ref: ref_tree.nodes.remove(math_ref)

                math = new_node(tree, m, 'math', 'ShaderNodeGroup', 'Math')
                dirty = True
            else:
                math, dirty = check_new_node(tree, m, 'math', 'ShaderNodeGroup', 'Math', True)

            if dirty:
                if channel_type == 'VALUE':
                    math.node_tree = get_node_tree_lib(lib.MOD_MATH_VALUE)
                else :
                    math.node_tree = get_node_tree_lib(lib.MOD_MATH)

                duplicate_lib_node_tree(math)
                math.inputs[2].default_value = m.math_r_val

                math.node_tree.nodes.get('Math.R').operation = m.math_meth
                math.node_tree.nodes.get('Math.A').operation = m.math_meth

                math.node_tree.nodes.get('Math.R').use_clamp = m.use_clamp
                math.node_tree.nodes.get('Math.A').use_clamp = m.use_clamp

                math.node_tree.nodes.get('Mix.A').mute = not m.affect_alpha

                if channel_type == 'VALUE':
                    math.inputs[3].default_value = m.math_a_val
                else:
                    math.inputs[3].default_value = m.math_g_val
                    math.inputs[4].default_value = m.math_b_val
                    math.inputs[5].default_value = m.math_a_val

                    math.node_tree.nodes.get('Math.G').operation = m.math_meth
                    math.node_tree.nodes.get('Math.B').operation = m.math_meth

                    math.node_tree.nodes.get('Math.G').use_clamp = m.use_clamp
                    math.node_tree.nodes.get('Math.B').use_clamp = m.use_clamp

                load_math_anim_props(tree, m, channel_type)

def check_yp_modifier_linear_nodes(yp):
    for ch in yp.channels:
        check_modifiers_trees(ch)
        
    for layer in yp.layers:
        check_modifiers_trees(layer)
        for ch in layer.channels:
            check_modifiers_trees(ch)
        #for mask in layer.masks:
        #    check_modifiers_trees(mask)

def delete_modifier_nodes(tree, mod):

    # Delete the nodes
    remove_node(tree, mod, 'frame')

    if mod.type == 'RGB_TO_INTENSITY':
        remove_node(tree, mod, 'rgb2i')

    elif mod.type == 'INTENSITY_TO_RGB':
        remove_node(tree, mod, 'i2rgb')

    elif mod.type == 'OVERRIDE_COLOR':
        remove_node(tree, mod, 'oc')

    elif mod.type == 'INVERT':
        remove_node(tree, mod, 'invert')

    elif mod.type == 'COLOR_RAMP':
        remove_node(tree, mod, 'color_ramp_linear_start')
        remove_node(tree, mod, 'color_ramp')
        remove_node(tree, mod, 'color_ramp_linear')
        remove_node(tree, mod, 'color_ramp_alpha_multiply')
        remove_node(tree, mod, 'color_ramp_mix_rgb') # Deprecated
        remove_node(tree, mod, 'color_ramp_mix_alpha') # Deprecated

    elif mod.type == 'RGB_CURVE':
        remove_node(tree, mod, 'rgb_curve')

    elif mod.type == 'HUE_SATURATION':
        remove_node(tree, mod, 'huesat')

    elif mod.type == 'BRIGHT_CONTRAST':
        remove_node(tree, mod, 'brightcon')

    elif mod.type == 'MULTIPLIER':
        remove_node(tree, mod, 'multiplier')

    elif mod.type == 'MATH':
        remove_node(tree, mod, 'math')

def create_modifier_tree(name):

    # Create modifier tree
    mod_tree = bpy.data.node_groups.new('.yP Modifiers ' + name, 'ShaderNodeTree')

    new_tree_input(mod_tree, 'RGB', 'NodeSocketColor')
    new_tree_input(mod_tree, 'Alpha', 'NodeSocketFloat')
    new_tree_output(mod_tree, 'RGB', 'NodeSocketColor')
    new_tree_output(mod_tree, 'Alpha', 'NodeSocketFloat')

    # New inputs and outputs
    mod_tree_start = mod_tree.nodes.new('NodeGroupInput')
    mod_tree_start.name = MOD_TREE_START
    mod_tree_end = mod_tree.nodes.new('NodeGroupOutput')
    mod_tree_end.name = MOD_TREE_END

    return mod_tree

def check_layer_modifier_tree(layer):

    yp = layer.id_data.yp

    if layer.source_group != '':
        layer_tree = get_source_tree(layer)
    else: layer_tree = get_tree(layer)

    # Get socket name used by the channel inputs
    socket_names = []
    for i, ch in enumerate(layer.channels):
        if not ch.enable: continue
        root_ch = yp.channels[i]

        # Get channel socket name
        if layer.type == 'PREV_LAYERS':
            socket_name = root_ch.name
        else: socket_name = get_channel_input_socket_name(layer, ch)

        if socket_name not in socket_names:
            socket_names.append(socket_name)

    num_groups = len(layer.mod_groups)
    num_socs = len(socket_names)

    # Get first group tree
    mod_group = layer_tree.nodes.get(layer.mod_groups[0].name) if num_groups > 0 else None
    mod_tree = mod_group.node_tree if mod_group else None

    if num_socs > 1 and len(layer.modifiers) > 0:
        # Refresh groups
        if num_socs != num_groups:

            if not mod_tree:
                mod_tree = create_modifier_tree(layer.name)

                # Move modifiers to modifier tree
                for mod in layer.modifiers:
                    check_modifier_nodes(mod, mod_tree, layer_tree)

            if num_socs > num_groups:
                # Create new mod groups
                for i in range(num_groups, num_socs):
                    mg = layer.mod_groups.add()
                    mgn = new_node(layer_tree, mg, 'name', 'ShaderNodeGroup', 'modifier_group_' + str(i))
                    mgn.node_tree = mod_tree

            elif num_socs < num_groups:
                # Remove excess mod groups
                for i in reversed(range(num_socs, num_groups)):
                    mg = layer.mod_groups[i]
                    remove_node(layer_tree, mg, 'name')
                    layer.mod_groups.remove(i)

        elif mod_tree:
            # Update modifiers
            for mod in layer.modifiers:
                check_modifier_nodes(mod, mod_tree)

    else:
        if num_groups > 0:

            # Copy modifier nodes into the layer tree
            if mod_tree:
                for mod in layer.modifiers:
                    check_modifier_nodes(mod, layer_tree, mod_tree)

            # Remove mod groups
            if hasattr(layer, 'mod_groups'):
                for mg in layer.mod_groups:
                    remove_node(layer_tree, mg, 'name')
                layer.mod_groups.clear()

        else:
            # Update modifiers
            for mod in layer.modifiers:
                check_modifier_nodes(mod, layer_tree)

def check_modifiers_trees(parent, rearrange=False):
    group_tree = parent.id_data
    yp = group_tree.yp

    enable_tree = False
    is_layer = False

    match1 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', parent.path_from_id())
    match2 = re.match(r'^yp\.layers\[(\d+)\]$', parent.path_from_id())

    if match1:
        layer = yp.layers[int(match1.group(1))]
        root_ch = yp.channels[int(match1.group(2))]
        ch = parent
        name = root_ch.name + ' ' + layer.name
        parent_tree = get_tree(layer)

    elif match2:
        layer = parent
        name = layer.name
        check_layer_modifier_tree(layer)
        return
        if layer.type not in {'IMAGE', 'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'MUSGRAVE'}:
            enable_tree = True
        if layer.source_group != '':
            parent_tree = get_source_tree(layer)
        else: parent_tree = get_tree(layer)
        is_layer=True

    else:
        parent_tree = group_tree

    if len(parent.modifiers) == 0:
        enable_tree = False

    mod_group = None
    if hasattr(parent, 'mod_groups'):
        if len(parent.mod_groups) > 0:
            mod_group = parent_tree.nodes.get(parent.mod_groups[0].name)
    elif hasattr(parent, 'mod_group'):
        mod_group = parent_tree.nodes.get(parent.mod_group)

    if enable_tree:
        if mod_group:
            for mod in parent.modifiers:
                check_modifier_nodes(mod, mod_group.node_tree)
        else:
            enable_modifiers_tree(parent, parent_tree, name, is_layer)
    else:
        if not mod_group:
            for mod in parent.modifiers:
                check_modifier_nodes(mod, parent_tree)
        else:
            disable_modifiers_tree(parent, parent_tree)

    if rearrange:
        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

def add_new_modifier(parent, modifier_type):

    yp = parent.id_data.yp

    match1 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', parent.path_from_id())
    match2 = re.match(r'^yp\.layers\[(\d+)\]$', parent.path_from_id())
    match3 = re.match(r'^yp\.channels\[(\d+)\]$', parent.path_from_id())

    if match1: 
        root_ch = yp.channels[int(match1.group(2))]
        channel_type = root_ch.type
    elif match3:
        root_ch = yp.channels[int(match3.group(1))]
        channel_type = root_ch.type
    elif match2:
        channel_type = 'RGB'
    
    tree = get_mod_tree(parent)
    modifiers = parent.modifiers

    # Add new modifier and move it to the top
    m = modifiers.add()

    if channel_type == 'VALUE' and modifier_type == 'OVERRIDE_COLOR':
        name = 'Override Value'
    else: name = [mt[1] for mt in modifier_type_items if mt[0] == modifier_type][0]

    m.name = get_unique_name(name, modifiers)
    modifiers.move(len(modifiers)-1, 0)
    shift_modifier_fcurves_down(parent)
    m = modifiers[0]
    m.type = modifier_type

    # Color ramp modifier has affect_color and affect_alpha enabled by default
    if modifier_type == 'COLOR_RAMP':
        ori_halt_update = yp.halt_update
        yp.halt_update = True

        # Used by alpha will defaulted to only affect the alpha channel
        used_by_alpha = is_modifier_used_by_alpha_channel(m)

        if used_by_alpha:
            m.affect_color = False
        else: m.affect_color = True

        m.affect_alpha = True

        yp.halt_update = ori_halt_update

    check_modifiers_trees(parent)

    return m

