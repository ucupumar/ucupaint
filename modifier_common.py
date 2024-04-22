import bpy
from .common import *
from . import lib

def get_modifier_channel_type(mod, return_non_color=False):

    yp = mod.id_data.yp
    match1 = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())
    match2 = re.match(r'yp\.channels\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())
    match3 = re.match(r'yp\.layers\[(\d+)\]\.modifiers\[(\d+)\]', mod.path_from_id())
    match4 = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.modifiers_1\[(\d+)\]', mod.path_from_id())

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

    elif match4:
        non_color = True
        channel_type = 'RGB'

    if return_non_color:
        return channel_type, non_color

    return channel_type

def check_modifier_nodes(m, tree, ref_tree=None):

    yp = m.id_data.yp
    nodes = tree.nodes

    # Get channel type and non color status
    channel_type, non_color = get_modifier_channel_type(m, True)

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
            remove_node(tree, m, 'rgb2i')
        else:
            if ref_tree:
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
                else: rgb2i.inputs['Gamma'].default_value = 1.0/GAMMA

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
                else: oc.inputs['Gamma'].default_value = 1.0/GAMMA

    elif m.type == 'COLOR_RAMP':

        if not m.enable:

            if ref_tree:
                color_ramp = new_node(tree, m, 'color_ramp', 'ShaderNodeValToRGB', 'ColorRamp')
                color_ramp_ref = ref_tree.nodes.get(m.color_ramp)
                if color_ramp_ref:
                    copy_node_props(color_ramp_ref, color_ramp)
                    ref_tree.nodes.remove(color_ramp_ref)

            remove_node(tree, m, 'color_ramp_linear_start')
            remove_node(tree, m, 'color_ramp_linear')
            remove_node(tree, m, 'color_ramp_alpha_multiply')
            remove_node(tree, m, 'color_ramp_mix_rgb')
            remove_node(tree, m, 'color_ramp_mix_alpha')
        else:
            if ref_tree:
                color_ramp_alpha_multiply_ref = ref_tree.nodes.get(m.color_ramp_alpha_multiply)
                color_ramp_linear_start_ref = ref_tree.nodes.get(m.color_ramp_linear_start)
                color_ramp_ref = ref_tree.nodes.get(m.color_ramp)
                color_ramp_linear_ref = ref_tree.nodes.get(m.color_ramp_linear)
                color_ramp_mix_alpha_ref = ref_tree.nodes.get(m.color_ramp_mix_alpha)
                color_ramp_mix_rgb_ref = ref_tree.nodes.get(m.color_ramp_mix_rgb)

                # Create new nodes if reference is used
                color_ramp_alpha_multiply = new_mix_node(tree, m, 'color_ramp_alpha_multiply', 'ColorRamp Alpha Multiply')
                color_ramp_linear_start = new_node(tree, m, 'color_ramp_linear_start', 'ShaderNodeGamma', 'ColorRamp Linear Start')
                color_ramp = new_node(tree, m, 'color_ramp', 'ShaderNodeValToRGB', 'ColorRamp')
                color_ramp_linear = new_node(tree, m, 'color_ramp_linear', 'ShaderNodeGamma', 'ColorRamp Linear')
                color_ramp_mix_alpha = new_mix_node(tree, m, 'color_ramp_mix_alpha', 'ColorRamp Mix Alpha')
                color_ramp_mix_rgb = new_mix_node(tree, m, 'color_ramp_mix_rgb', 'ColorRamp Mix RGB')
                dirty = True
                ramp_dirty = False
            else:

                color_ramp_alpha_multiply, dirty = check_new_mix_node(tree, m, 'color_ramp_alpha_multiply', 'ColorRamp Alpha Multiply', True)
                color_ramp_linear_start = check_new_node(tree, m, 'color_ramp_linear_start', 'ShaderNodeGamma', 'ColorRamp Linear Start')
                color_ramp, ramp_dirty = check_new_node(tree, m, 'color_ramp', 'ShaderNodeValToRGB', 'ColorRamp', True)
                color_ramp_linear = check_new_node(tree, m, 'color_ramp_linear', 'ShaderNodeGamma', 'ColorRamp Linear')
                color_ramp_mix_alpha = check_new_mix_node(tree, m, 'color_ramp_mix_alpha', 'ColorRamp Mix Alpha')
                color_ramp_mix_rgb = check_new_mix_node(tree, m, 'color_ramp_mix_rgb', 'ColorRamp Mix RGB')

            if ref_tree:

                if color_ramp_alpha_multiply_ref:
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

                if color_ramp_mix_alpha_ref:
                    copy_node_props(color_ramp_mix_alpha_ref, color_ramp_mix_alpha)
                    ref_tree.nodes.remove(color_ramp_mix_alpha_ref)

                if color_ramp_mix_rgb_ref:
                    copy_node_props(color_ramp_mix_rgb_ref, color_ramp_mix_rgb)
                    ref_tree.nodes.remove(color_ramp_mix_rgb_ref)

            if dirty:

                color_ramp_alpha_multiply.inputs[0].default_value = 1.0
                color_ramp_alpha_multiply.blend_type = 'MULTIPLY'
                color_ramp_mix_alpha.inputs[0].default_value = 1.0
                color_ramp_mix_rgb.inputs[0].default_value = 1.0

            if non_color or yp.use_linear_blending:
                remove_node(tree, m, 'color_ramp_linear_start')
                remove_node(tree, m, 'color_ramp_linear')
            else: 
                color_ramp_linear_start.inputs[1].default_value = GAMMA
                color_ramp_linear.inputs[1].default_value = 1.0/GAMMA

            if ramp_dirty:
                # Set default color if ramp just created
                color_ramp.color_ramp.elements[0].color = (0,0,0,0) 

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
            remove_node(tree, m, 'huesat')
        else:
            if ref_tree:
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

    elif m.type == 'BRIGHT_CONTRAST':

        if not m.enable:
            remove_node(tree, m, 'brightcon')
        else:
            if ref_tree:
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
            remove_node(tree, m, 'math')
        else:
            if ref_tree:
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
        remove_node(tree, mod, 'color_ramp_mix_rgb')
        remove_node(tree, mod, 'color_ramp_mix_alpha')

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

