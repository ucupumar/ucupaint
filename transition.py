import bpy
from bpy.props import *
from .common import *
from .transition_common import *
from .node_connections import *
from .node_arrangements import *
from .subtree import *

def update_transition_ramp_intensity_value(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)

    set_ramp_intensity_value(tree, layer, self)

def update_transition_bump_crease_factor(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    root_ch = yp.channels[int(match.group(2))]
    tree = get_tree(layer)
    ch = self

    if not ch.enable_transition_bump or not ch.enable or not ch.transition_bump_crease or ch.transition_bump_flip: return

    height_proc = tree.nodes.get(ch.height_proc)
    if height_proc:
        height_proc.inputs['Crease Factor'].default_value = ch.transition_bump_crease_factor
        if ch.normal_map_type != 'NORMAL_MAP':
            height_proc.inputs['Transition Max Height'].default_value = get_transition_bump_max_distance(ch)
            height_proc.inputs['Delta'].default_value = get_transition_disp_delta(layer, ch)

    #normal_proc = tree.nodes.get(ch.normal_proc)
    #if normal_proc:
    #    normal_proc.inputs['Crease Factor'].default_value = ch.transition_bump_crease_factor
    #    if ch.normal_map_type != 'NORMAL_MAP':
    #        normal_proc.inputs['Transition Max Height'].default_value = get_transition_bump_max_distance(ch)
    #        normal_proc.inputs['Delta'].default_value = get_transition_disp_delta(layer, ch)
    #    #normal_proc.inputs['Crease Height Scale'].default_value = get_fine_bump_distance(
    #    #        ch.transition_bump_crease_factor * -ch.transition_bump_distance)

    #max_height = get_displacement_max_height(root_ch)
    #root_ch.displacement_height_ratio = max_height
    update_displacement_height_ratio(root_ch)

def update_transition_bump_crease_power(self, context):
    if not self.enable: return

    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    #root_ch = yp.channels[int(match.group(2))]
    tree = get_tree(layer)
    ch = self

    if not ch.enable_transition_bump or not ch.transition_bump_crease or ch.transition_bump_flip: return

    height_proc = tree.nodes.get(ch.height_proc)
    if height_proc:
        height_proc.inputs['Crease Power'].default_value = ch.transition_bump_crease_power

    #normal_proc = tree.nodes.get(ch.normal_proc)
    #if normal_proc:
    #    normal_proc.inputs['Crease Power'].default_value = ch.transition_bump_crease_power

def update_transition_bump_falloff_emulated_curve_fac(self, context):
    if not self.enable: return

    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    #root_ch = yp.channels[int(match.group(2))]
    tree = get_tree(layer)
    ch = self

    if not ch.enable_transition_bump or not ch.transition_bump_falloff: return

    val = get_transition_bump_falloff_emulated_curve_value(ch)

    tb_falloff = tree.nodes.get(ch.tb_falloff)
    if tb_falloff: 
        tb_falloff.inputs['Fac'].default_value = val

    #for d in neighbor_directions:
    #    tbf = tree.nodes.get(getattr(ch, 'tb_falloff_' + d))
    #    if tbf: tbf.inputs[1].default_value = val

def update_transition_bump_value(self, context):
    if not self.enable: return

    yp = self.id_data.yp
    if yp.halt_update: return
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    tree = get_tree(layer)
    ch = self

    if not ch.enable_transition_bump: return

    intensity_multiplier = tree.nodes.get(ch.intensity_multiplier)
    tb_intensity_multiplier = tree.nodes.get(ch.tb_intensity_multiplier)

    if ch.transition_bump_flip or layer.type=='BACKGROUND':
    #if ch.transition_bump_flip:
        #if intensity_multiplier: intensity_multiplier.inputs[1].default_value = ch.transition_bump_second_edge_value
        #if tb_intensity_multiplier: tb_intensity_multiplier.inputs[1].default_value = ch.transition_bump_value
        pass
    else:
        #if intensity_multiplier: intensity_multiplier.inputs[1].default_value = ch.transition_bump_value
        #if tb_intensity_multiplier: tb_intensity_multiplier.inputs[1].default_value = ch.transition_bump_second_edge_value
        pass
    if intensity_multiplier: intensity_multiplier.inputs[1].default_value = ch.transition_bump_value
    if tb_intensity_multiplier: tb_intensity_multiplier.inputs[1].default_value = ch.transition_bump_second_edge_value

    for c in layer.channels:
        set_transition_ramp_and_intensity_multiplier(tree, ch, c)

def update_transition_bump_distance(self, context):
    if not self.enable: return

    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    ch_index = int(match.group(2))
    root_ch = yp.channels[ch_index]
    ch = self
    tree = get_tree(layer)

    if not ch.enable_transition_bump: return

    disp_ch = get_root_height_channel(yp)
    if disp_ch == root_ch:

        #update_layer_bump_distance(ch, root_ch, layer, tree)

        #max_height = get_displacement_max_height(root_ch, layer)

        #height_proc = tree.nodes.get(self.height_proc)
        #if height_proc: #and 'Transition Max Height' in height_proc.inputs:
        #    if self.normal_map_type == 'NORMAL_MAP':
        #        height_proc.inputs['Bump Height'].default_value = get_transition_bump_max_distance(self)
        #    else:
        #        height_proc.inputs['Transition Max Height'].default_value = get_transition_bump_max_distance(self)
        #        height_proc.inputs['Delta'].default_value = get_transition_disp_delta(layer, self)

        #normal_proc = tree.nodes.get(self.normal_proc)
        #if normal_proc:
        #    normal_proc.inputs['Max Height'].default_value = max_height

        #    if root_ch.enable_smooth_bump:
        #        normal_proc.inputs['Bump Height Scale'].default_value = get_fine_bump_distance(max_height)

        #max_height = get_displacement_max_height(root_ch)
        #root_ch.displacement_height_ratio = max_height
        update_displacement_height_ratio(root_ch)

def update_transition_bump_chain(self, context):
    T = time.time()

    yp = self.id_data.yp
    if yp.halt_update: return
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    tree = get_tree(layer)
    root_ch = yp.channels[int(m.group(2))]
    ch = self

    #if ch.enable_transition_bump and ch.enable:

    #check_mask_mix_nodes(layer, tree)
    #check_mask_source_tree(layer) #, ch)

    # Trigger normal channel update
    #ch.normal_map_type = ch.normal_map_type
    check_channel_normal_map_nodes(tree, layer, root_ch, ch)

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer) #, mod_reconnect=True)

    print('INFO: Transition bump chain is updated at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def update_transition_bump_curved_offset(self, context):

    yp = self.id_data.yp
    if yp.halt_update: return
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    tree = get_tree(layer)
    ch = self

    #tb_bump = tree.nodes.get(ch.tb_bump)
    #if tb_bump:
    #    tb_bump.inputs['Offset'].default_value = ch.transition_bump_curved_offset

def update_transition_bump_fac(self, context):

    yp = self.id_data.yp
    if yp.halt_update: return
    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(m.group(1))]
    tree = get_tree(layer)
    ch = self

    bump_ch = get_transition_bump_channel(layer)
    if bump_ch: set_transition_ramp_and_intensity_multiplier(tree, bump_ch, ch)

def update_transition_ao_intensity(self, context):

    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    ch = self
    tree = get_tree(layer)

    mute = not layer.enable or not ch.enable

    tao = tree.nodes.get(ch.tao)
    if tao:
        tao.inputs['Intensity'].default_value = 0.0 if mute else get_transition_ao_intensity(ch)

def update_transition_ao_edge(self, context):

    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    ch = self
    tree = get_tree(layer)

    bump_ch = get_transition_bump_channel(layer)

    tao = tree.nodes.get(ch.tao)
    if tao and bump_ch:
        tao.inputs['Power'].default_value = ch.transition_ao_power

def update_transition_ao_color(self, context):

    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    ch = self
    tree = get_tree(layer)

    tao = tree.nodes.get(ch.tao)
    if tao:
        col = (ch.transition_ao_color.r, ch.transition_ao_color.g, ch.transition_ao_color.b, 1.0)
        tao.inputs['AO Color'].default_value = col

def update_transition_ao_exclude_inside(self, context):

    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    ch = self
    tree = get_tree(layer)

    tao = tree.nodes.get(ch.tao)
    if tao:
        tao.inputs['Exclude Inside'].default_value = 1.0 - ch.transition_ao_inside_intensity

def show_transition(self, context, ttype):
    if not hasattr(context, 'parent'): 
        self.report({'ERROR'}, "Context is incorrect!")
        return {'CANCELLED'}

    yp = context.parent.id_data.yp
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', context.parent.path_from_id())
    if not match: 
        self.report({'ERROR'}, "Context is incorrect!")
        return {'CANCELLED'}
    layer = yp.layers[int(match.group(1))]
    root_ch = yp.channels[int(match.group(2))]
    ch = context.parent

    bump_ch = get_transition_bump_channel(layer)

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
        for c in layer.channels:
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

    type : EnumProperty(
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

        yp = context.parent.id_data.yp
        match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', context.parent.path_from_id())
        if not match: 
            self.report({'ERROR'}, "Context is incorrect!")
            return {'CANCELLED'}
        layer = yp.layers[int(match.group(1))]
        root_ch = yp.channels[int(match.group(2))]
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

    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    ch = self

    tree = get_tree(layer)

    # Get transition bump
    bump_ch = get_transition_bump_channel(layer)

    check_transition_ao_nodes(tree, layer, ch, bump_ch)

    # Update mask multiply
    check_mask_mix_nodes(layer, tree)

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    if ch.enable_transition_ao:
        print('INFO: Transition AO is enabled at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')
    else: print('INFO: Transition AO is disabled at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def update_enable_transition_ramp(self, context):
    T = time.time()

    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    root_ch = yp.channels[int(match.group(2))]
    ch = self

    tree = get_tree(layer)

    check_transition_ramp_nodes(tree, layer, ch)

    # Update mask multiply
    check_mask_mix_nodes(layer, tree)

    check_blend_type_nodes(root_ch, layer, ch)

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    if ch.enable_transition_ramp:
        print('INFO: Transition ramp is enabled at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')
    else: print('INFO: Transition ramp is disabled at {:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def update_enable_transition_bump(self, context):
    T = time.time()

    yp = self.id_data.yp
    if yp.halt_update or not self.enable: return
    match = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    ch_index = int(match.group(2))
    root_ch = yp.channels[ch_index]
    ch = self
    tree = get_tree(layer)

    check_transition_bump_nodes(layer, tree, ch)

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer) #, mod_reconnect=True)

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
