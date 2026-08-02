import bpy
from .common import *
from .input_outputs import *
from bpy.props import *
from . import lib, ListItem

def get_preview(mat, output=None, advanced=False, normal_viewer=False, normal_space='CAMERA', use_alpha=False):
    tree = mat.node_tree

    # Search for output
    if not output:
        output = get_material_output(mat)

    if not output: return None

    if advanced:
        if normal_viewer:
            preview, dirty = simple_replace_new_node(
                tree, EMISSION_VIEWER, 'ShaderNodeGroup', 'Emission Viewer', 
                lib.ADVANCED_NORMAL_EMISSION_VIEWER,
                return_status=True, hard_replace=True
            )
        else:
            preview, dirty = simple_replace_new_node(
                tree, EMISSION_VIEWER, 'ShaderNodeGroup', 'Emission Viewer', 
                lib.ADVANCED_EMISSION_VIEWER,
                return_status=True, hard_replace=True
            )
        if dirty:
            duplicate_lib_node_tree(preview)
    else:
        if normal_viewer:
            preview, dirty = simple_replace_new_node(
                tree, EMISSION_VIEWER, 'ShaderNodeGroup', 'Emission Viewer', 
                lib.NORMAL_EMISSION_VIEWER,
                return_status=True, hard_replace=True
            )
            if dirty:
                duplicate_lib_node_tree(preview)
        elif use_alpha:
            preview, dirty = simple_replace_new_node(
                tree, EMISSION_VIEWER, 'ShaderNodeGroup', 'Emission Viewer', 
                lib.TRANSPARENT_EMISSION_VIEWER,
                return_status=True, hard_replace=True
            )
        else:
            preview, dirty = simple_replace_new_node(
                tree, EMISSION_VIEWER, 'ShaderNodeEmission', 'Emission Viewer', 
                return_status = True
            )

    # Update the normal space
    if normal_viewer:
        transform = preview.node_tree.nodes.get('Vector Transform')
        if transform: transform.convert_to = normal_space

    # Matcap mode will be applied for camera space
    inp = preview.inputs.get('Matcap Mode')
    if inp: inp.default_value = 1.0 if normal_space == 'CAMERA' else 0.0

    if dirty:
        preview.hide = True
        preview.location = (output.location.x, output.location.y + 30.0)

    if output.inputs[0].links:

        # Remember output and original bsdf
        ori_bsdf = output.inputs[0].links[0].from_node
        ori_socket = output.inputs[0].links[0].from_socket
        ori_bsdf_output_index = 0
        for i, outp in enumerate(ori_bsdf.outputs):
            if outp == ori_socket:
                ori_bsdf_output_index = i

        # Only remember original BSDF if its not the preview node itself
        if ori_bsdf != preview:
            mat.yp.ori_bsdf = ori_bsdf.name
            mat.yp.ori_bsdf_output_index = ori_bsdf_output_index

    return preview

def remove_preview(mat, advanced=False):
    nodes = mat.node_tree.nodes
    preview = nodes.get(EMISSION_VIEWER)
    scene = bpy.context.scene

    if preview: 
        # NOTE: Make sure to not remove preview images since it can cause crash when preview mode is enabled again
        simple_remove_node(mat.node_tree, preview, remove_images=False)
        bsdf = nodes.get(mat.yp.ori_bsdf)
        output = get_material_output(mat)
        mat.yp.ori_bsdf = ''

        if bsdf and output:
            mat.node_tree.links.new(bsdf.outputs[mat.yp.ori_bsdf_output_index], output.inputs[0])

        # Recover view transform
        if scene.yp.ori_view_transform != '':
            scene.view_settings.view_transform = scene.yp.ori_view_transform
            scene.yp.ori_view_transform = ''

            scene.display_settings.display_device = scene.yp.ori_display_device
            scene.view_settings.look = scene.yp.ori_look
            scene.view_settings.exposure = scene.yp.ori_exposure
            scene.view_settings.gamma = scene.yp.ori_gamma
            scene.view_settings.use_curve_mapping = scene.yp.ori_use_curve_mapping
            if is_bl_newer_than(5):
                if scene.yp.ori_compositing_node_name != '':
                    cng = bpy.data.node_groups.get(scene.yp.ori_compositing_node_name)
                    if cng: scene.compositing_node_group = cng
                    scene.yp.ori_compositing_node_name = ''
            else: scene.use_nodes = scene.yp.ori_use_compositing

def set_srgb_view_transform():
    scene = bpy.context.scene

    ypup = get_user_preferences()

    # Set view transform to srgb
    if scene.yp.ori_view_transform == '' and ypup.make_preview_mode_srgb:

        scene.yp.ori_look = scene.view_settings.look
        scene.view_settings.look = 'None'

        if is_bl_newer_than(5):
            if scene.compositing_node_group:
                scene.yp.ori_compositing_node_name = scene.compositing_node_group.name
                scene.compositing_node_group = None
        else:
            scene.yp.ori_use_compositing = scene.use_nodes
            scene.use_nodes = False

        scene.yp.ori_view_transform = scene.view_settings.view_transform
        if is_bl_newer_than(2, 80):
            try: scene.view_settings.view_transform = 'Standard'
            except Exception as e: print(e)
        else: 
            try: scene.view_settings.view_transform = 'Default'
            except Exception as e: print(e)

        scene.yp.ori_display_device = scene.display_settings.display_device
        try: scene.display_settings.display_device = 'sRGB'
        except Exception as e: print(e)

        scene.yp.ori_exposure = scene.view_settings.exposure
        scene.view_settings.exposure = 0.0

        scene.yp.ori_gamma = scene.view_settings.gamma
        scene.view_settings.gamma = 1.0

        scene.yp.ori_use_curve_mapping = scene.view_settings.use_curve_mapping
        scene.view_settings.use_curve_mapping = False

def update_layer_preview_mode(self, context):
    yp = self
    mat = get_active_material()

    if is_yp_on_material(yp, mat):
        group_node = get_active_ypaint_node()
    else:
        mats = get_materials_using_yp(yp)
        if not mats: return
        mat = mats[0]
        group_nodes = get_nodes_using_yp(mat, yp)
        if not group_nodes: return
        group_node = group_nodes[0]

    tree = mat.node_tree
    index = yp.preview_mode_channel_index
    channel = yp.channels[index]
    layer = ListItem.get_active_layer(yp)

    if yp.preview_mode and yp.layer_preview_mode:
        yp.preview_mode = False

    # Get preview node
    if yp.layer_preview_mode:

        check_all_channel_ios(yp, specific_layer=layer) #, do_process_layers=layer!=None)

        # Set view transform to srgb so color picker won't pick wrong color
        set_srgb_view_transform()

        output = get_material_output(mat, create_one=True)
        if yp.layer_preview_mode_type in {'ALPHA', 'SPECIFIC_MASK'}:
            preview = get_preview(mat, output, False)
            if not preview: return

            tree.links.new(group_node.outputs[LAYER_ALPHA_VIEWER], preview.inputs[0])
            tree.links.new(preview.outputs[0], output.inputs[0])

        else:
            ch = layer.channels[yp.preview_mode_channel_index] if layer else None
            normal_ch, height_ch = get_layer_normal_height_ch_pairs(layer) if layer else None, None

            if channel.special_type == 'NORMAL':
                preview = get_preview(mat, output, True, True, normal_space=yp.preview_mode_normal_space)
            else:
                preview = get_preview(mat, output, True)
            if not preview: return

            tree.links.new(group_node.outputs[LAYER_VIEWER], preview.inputs[0])
            tree.links.new(group_node.outputs[LAYER_ALPHA_VIEWER], preview.inputs[1])
            tree.links.new(preview.outputs[0], output.inputs[0])

            # Set gamma
            if 'Gamma' in preview.inputs:
                if channel.colorspace != 'LINEAR' and not yp.use_linear_blending:
                    if preview.inputs['Gamma'].default_value != 2.2:
                        preview.inputs['Gamma'].default_value = 2.2
                else: 
                    if preview.inputs['Gamma'].default_value != 1.0:
                        preview.inputs['Gamma'].default_value = 1.0

            # Set channel layer blending
            #mix = preview.node_tree.nodes.get('Mix')
            #mix.blend_type = ch.blend_type
            blend_type = ch.blend_type if ch else 'MIX'
            update_preview_mix(blend_type, preview)

            if ch:
                if ch == normal_ch and height_ch.enable and height_ch.use_height_as_normal:
                    channel_enabled = True
                else: channel_enabled = get_channel_enabled(ch, layer)
            else: channel_enabled = True

            # Use different grid if channel is not enabled
            preview.inputs['Missing Data'].default_value = 1.0 if (not channel_enabled or (layer and not layer.enable)) else 0.0

    else:
        check_all_channel_ios(yp)
        remove_preview(mat)

def update_preview_mode(self, context):
    yp = self
    mat = get_active_material()

    if is_yp_on_material(yp, mat):
        group_node = get_active_ypaint_node()
    else:
        mats = get_materials_using_yp(yp)
        if not mats: return
        mat = mats[0]
        group_nodes = get_nodes_using_yp(mat, yp)
        if not group_nodes: return
        group_node = group_nodes[0]

    tree = mat.node_tree
    index = yp.preview_mode_channel_index
    channel = yp.channels[index]

    if yp.layer_preview_mode and yp.preview_mode:
        yp.layer_preview_mode = False

    if self.preview_mode:

        # Check if alpha is needed to use
        color_ch, alpha_ch = get_color_alpha_ch_pairs(yp)
        use_alpha = alpha_ch != None and channel != alpha_ch and yp.preview_mode_use_alpha

        # Set view transform to srgb so color picker won't pick wrong color
        set_srgb_view_transform()

        output = get_material_output(mat, create_one=True)

        # Get preview node by name first
        preview = mat.node_tree.nodes.get(EMISSION_VIEWER)

        # Try to get socket that connected to preview first input
        if preview:
            from_socket = [link.from_socket for link in preview.inputs[0].links]
            if from_socket: from_socket = from_socket[0]
        else: from_socket = None

        # Check if there's any valid socket connected to first input of preview node
        is_from_socket_missing = not from_socket or (from_socket and not from_socket.name.startswith(channel.name))

        # Get all outputs from current channel
        outs = [o for o in group_node.outputs if o.name.startswith(channel.name)]

        # Use special preview for normal
        if channel.special_type == 'NORMAL' and (is_from_socket_missing or (from_socket and from_socket == outs[-1])):
            preview = get_preview(mat, output, False, True, normal_space=yp.preview_mode_normal_space, use_alpha=use_alpha)
        else: preview = get_preview(mat, output, False, use_alpha=use_alpha)

        # Preview should exists by now
        if not preview: return

        # Make sure needed output exists
        check_all_channel_ios(yp)

        if is_from_socket_missing:
            # Connect first output
            tree.links.new(group_node.outputs[channel.name], preview.inputs[0])
        else:
            # Cycle outputs
            for i, o in enumerate(outs):
                if o == from_socket:
                    if i != len(outs) - 1:
                        tree.links.new(outs[i + 1], preview.inputs[0])
                    else: tree.links.new(outs[0], preview.inputs[0])

        # Alpha setup
        alpha_inp = preview.inputs.get('Alpha')
        if alpha_inp:
            if use_alpha:
                alpha_outp = group_node.outputs.get(alpha_ch.name)
                if alpha_outp: tree.links.new(alpha_outp, alpha_inp)
            else:
                for link in alpha_inp.links:
                    tree.links.remove(link)

        tree.links.new(preview.outputs[0], output.inputs[0])
    else:
        check_all_channel_ios(yp)
        remove_preview(mat)

def update_preview_mode_options(self, context):
    if self.layer_preview_mode:
        update_layer_preview_mode(self, context)
    else: update_preview_mode(self, context)

def update_layer_preview_mode_type(self, context):
    if self.layer_preview_mode:
        update_layer_preview_mode(self, context)

def update_preview_mode_channel_index(self, context):
    yp = self

    if yp.preview_mode: update_preview_mode(yp, context)
    elif yp.layer_preview_mode: update_layer_preview_mode(yp, context)

class BasePreviewMode():
    preview_mode : BoolProperty(
        name = 'Enable Channel Preview Mode',
        description = 'Enable channel preview mode',
        default = False,
        update = update_preview_mode
    )

    preview_mode_normal_space : EnumProperty(
        name = 'Preview Mode Normal Space',
        description = 'Preview mode space to normal channel',
        items = (
            ('CAMERA', 'View Space', 'Encode normal output and transform it into view space.\nNOTE: This also will apply special calculation to make the output looks like a matcap shader.'),
            ('WORLD', 'World Space', 'Encode normal output and transform it into world space'),
            ('OBJECT', 'Object Space', 'Encode normal output and transform it into object space'),
        ),
        default = 'CAMERA',
        update = update_preview_mode_options
    )

    preview_mode_use_alpha : BoolProperty(
        name = 'Preview Mode Use Alpha',
        description = 'Use alpha channel for preview mode',
        default = False,
        update = update_preview_mode_options
    )

    # Layer Preview Mode
    layer_preview_mode : BoolProperty(
        name = 'Enable Layer Preview Mode',
        description = 'Enable layer preview mode',
        default = False,
        update = update_layer_preview_mode
    )

    layer_preview_mode_type : EnumProperty(
        name = 'Layer Preview Mode Type',
        description = 'Layer preview mode type',
        items = (
            ('LAYER', 'Layer', ''),
            ('ALPHA', 'Alpha', ''),
            ('SPECIFIC_MASK', 'Active Mask / Custom Data', ''),
        ),
        default = 'LAYER',
        update = update_layer_preview_mode_type
    )

    ori_layer_preview_mode : BoolProperty(
        name = 'Original value for Layer Preview Mode',
        description = 'Original value for layer preview mode',
        default = False
    )

    preview_mode_channel_index : IntProperty(
        name = 'Preview Mode Channel Index',
        description = 'preview mode channel index',
        default = 0,
        update = update_preview_mode_channel_index
    )

class YSelectPreviewModeChannel(bpy.types.Operator):
    bl_idname = "wm.y_select_preview_mode_channel"
    bl_label = "Select Preview Mode Channel"
    bl_description = "Select preview mode channel"
    bl_options = {'REGISTER', 'UNDO'}

    channel_idx : IntProperty(
        name = 'Channel Index',
        description = 'Channel index',
        default = 0
    )

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return group_node and len(group_node.node_tree.yp.channels) > 0

    def execute(self, context):
        group_node = get_active_ypaint_node()
        yp = group_node.node_tree.yp

        yp.preview_mode_channel_index = self.channel_idx
        return{'FINISHED'}

def register():
    bpy.utils.register_class(YSelectPreviewModeChannel)

def unregister():
    bpy.utils.unregister_class(YSelectPreviewModeChannel)
