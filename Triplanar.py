import bpy, re
from . import lib
from bpy.props import *
from .common import *
from .node_connections import create_link

def refresh_triplanar_wrapper(wrapper, source_tree):
    ''' Make sure triplanar wrapper interface mirrors the source tree outputs
    and its internal nodes sample the source tree three times '''

    # Vector input should be the first socket
    inp = get_tree_input_by_name(wrapper, 'Vector')
    if not inp: new_tree_input(wrapper, 'Vector', 'NodeSocketVector')

    valid_input_names = ['Vector'] + list(triplanar_input_props)
    for socket_name in triplanar_input_props:
        inp = get_tree_input_by_name(wrapper, socket_name)
        if not inp:
            inp = new_tree_input(wrapper, socket_name, 'NodeSocketFloatFactor')
            inp.min_value = 0.0
            inp.max_value = 1.0
            inp.default_value = triplanar_input_defaults.get(socket_name, 1.0)

    for inp in reversed(get_tree_inputs(wrapper)):
        if inp.name not in valid_input_names:
            remove_tree_input(wrapper, inp)

    # Mirror source tree outputs
    valid_output_names = []
    for outp in get_tree_outputs(source_tree):
        tout = get_tree_output_by_name(wrapper, outp.name)
        if not tout:
            socket_type = 'NodeSocketFloat' if outp.name.endswith(io_suffix['ALPHA']) or outp.name == 'Value' else 'NodeSocketColor'
            new_tree_output(wrapper, outp.name, socket_type)
        valid_output_names.append(outp.name)

    for outp in reversed(get_tree_outputs(wrapper)):
        if outp.name not in valid_output_names:
            remove_tree_output(wrapper, outp)

    start = wrapper.nodes.get(TREE_START)
    end = wrapper.nodes.get(TREE_END)

    # Prep node
    prep = wrapper.nodes.get(TRIPLANAR_PREP)
    if not prep:
        prep = wrapper.nodes.new('ShaderNodeGroup')
        prep.name = TRIPLANAR_PREP
        prep.label = TRIPLANAR_PREP
    prep_tree = lib.get_triplanar_prep_tree()
    if prep.node_tree != prep_tree: prep.node_tree = prep_tree

    create_link(wrapper, start.outputs['Vector'], prep.inputs['Vector'])
    for socket_name in triplanar_input_props:
        create_link(wrapper, start.outputs[socket_name], prep.inputs[socket_name])

    # Source instances
    sources = {}
    for i, axis in enumerate(triplanar_axes):
        source = wrapper.nodes.get(TRIPLANAR_SOURCE_PREFIX + axis)
        if not source:
            source = wrapper.nodes.new('ShaderNodeGroup')
            source.name = TRIPLANAR_SOURCE_PREFIX + axis
            source.label = TRIPLANAR_SOURCE_PREFIX + axis
        if source.node_tree != source_tree: source.node_tree = source_tree
        source.location = (400, -i * 300)
        create_link(wrapper, prep.outputs['Vector ' + axis], source.inputs[0])
        sources[axis] = source

    # Blend node per source tree output pair
    alpha_pair_names = [name + io_suffix['ALPHA'] for name in valid_output_names]
    main_output_names = [name for name in valid_output_names if name not in alpha_pair_names]
    valid_blend_names = []
    for i, name in enumerate(main_output_names):
        alpha_name = name + io_suffix['ALPHA']
        paired = alpha_name in valid_output_names

        blend = wrapper.nodes.get(TRIPLANAR_BLEND_PREFIX + name)
        if not blend:
            blend = wrapper.nodes.new('ShaderNodeGroup')
            blend.name = TRIPLANAR_BLEND_PREFIX + name
            blend.label = TRIPLANAR_BLEND_PREFIX + name
        blend_tree = lib.get_triplanar_blend_tree() if paired else lib.get_triplanar_blend_value_tree()
        if blend.node_tree != blend_tree: blend.node_tree = blend_tree
        blend.location = (700, -i * 300)
        valid_blend_names.append(blend.name)

        for axis in triplanar_axes:
            if paired:
                create_link(wrapper, sources[axis].outputs[name], blend.inputs['Color ' + axis])
                create_link(wrapper, sources[axis].outputs[alpha_name], blend.inputs['Alpha ' + axis])
                create_link(wrapper, prep.outputs['Color Weight ' + axis], blend.inputs['Color Weight ' + axis])
                create_link(wrapper, prep.outputs['Alpha Weight ' + axis], blend.inputs['Alpha Weight ' + axis])
            else:
                create_link(wrapper, sources[axis].outputs[name], blend.inputs['Value ' + axis])
                create_link(wrapper, prep.outputs['Alpha Weight ' + axis], blend.inputs['Weight ' + axis])

        if paired:
            create_link(wrapper, blend.outputs['Color'], end.inputs[name])
            create_link(wrapper, blend.outputs['Alpha'], end.inputs[alpha_name])
        else:
            create_link(wrapper, blend.outputs['Value'], end.inputs[name])

    # Remove unused blend nodes
    for node in [n for n in wrapper.nodes if n.name.startswith(TRIPLANAR_BLEND_PREFIX)]:
        if node.name not in valid_blend_names:
            wrapper.nodes.remove(node)

    start.location = (0, 0)
    prep.location = (200, 0)
    end.location = (1000, 0)

def get_triplanar_instances(entity, tree):
    ''' Get all group nodes sharing the entity source tree '''

    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())
    group_prop = 'group_node' if m2 else 'source_group'

    instances = []
    names = [getattr(entity, group_prop)] + [getattr(entity, 'source_' + d) for d in neighbor_directions]
    for name in names:
        node = tree.nodes.get(name)
        if node and node.type == 'GROUP' and node.node_tree:
            instances.append(node)

    return instances

def check_entity_triplanar_nodes(entity, tree=None):
    ''' Wrap or unwrap the entity source tree with a triplanar wrapper '''

    yp = entity.id_data.yp

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1:
        entity_enabled = get_layer_enabled(entity)
        layer = entity
        prefix = LAYERGROUP_PREFIX
    elif m2:
        entity_enabled = get_mask_enabled(entity)
        layer = yp.layers[int(m2.group(1))]
        prefix = MASKGROUP_PREFIX
    else: return

    if not tree: tree = get_tree(layer)
    if not tree: return

    instances = get_triplanar_instances(entity, tree)
    if not instances: return

    # Instances can point to the source tree or a wrapper around it
    current_tree = instances[0].node_tree
    source_tree = get_triplanar_source_tree(current_tree)
    wrapper = current_tree if source_tree else None
    if not source_tree: source_tree = current_tree

    if entity_enabled and is_entity_using_triplanar(entity):
        if not wrapper:
            wrapper = bpy.data.node_groups.new(prefix + entity.name + ' Triplanar', 'ShaderNodeTree')
            create_essential_nodes(wrapper)

        refresh_triplanar_wrapper(wrapper, source_tree)

        for instance in instances:
            if instance.node_tree != wrapper: instance.node_tree = wrapper

    elif wrapper:
        for instance in instances:
            if instance.node_tree != source_tree: instance.node_tree = source_tree

        remove_datablock(bpy.data.node_groups, wrapper)

def unwrap_triplanar_group_node(group_node):
    ''' Point the group node back to the actual source tree and delete the wrapper '''

    if not group_node or group_node.type != 'GROUP': return
    source_tree = get_triplanar_source_tree(group_node.node_tree)
    if source_tree:
        wrapper = group_node.node_tree
        group_node.node_tree = source_tree
        remove_datablock(bpy.data.node_groups, wrapper)

def duplicate_triplanar_inner_tree(wrapper):
    ''' Duplicate the source tree inside a copied triplanar wrapper so it's no longer shared '''

    inner_tree = get_triplanar_source_tree(wrapper)
    if not inner_tree: return None

    inner_copy = inner_tree.copy()
    for axis in triplanar_axes:
        source = wrapper.nodes.get(TRIPLANAR_SOURCE_PREFIX + axis)
        if source: source.node_tree = inner_copy

    return inner_copy

class BaseTriplanar():

    triplanar_blend : FloatProperty(
        name = 'Triplanar Blend',
        description = 'Blend smoothness between triplanar projection axes',
        subtype = 'FACTOR',
        min=0.0, max=1.0, default=0.2, precision=3
    )

    triplanar_expand : FloatProperty(
        name = 'Triplanar Expand',
        description = 'Expand the coverage of shown sides to counteract fading when some sides are hidden',
        subtype = 'FACTOR',
        min=0.0, max=1.0, default=0.0, precision=3
    )

    triplanar_show_pos_x : FloatProperty(
        name = 'Show +X',
        description = 'Show triplanar projection on faces pointing along the object +X axis',
        subtype = 'FACTOR',
        min=0.0, max=1.0, default=1.0, precision=3
    )

    triplanar_show_neg_x : FloatProperty(
        name = 'Show -X',
        description = 'Show triplanar projection on faces pointing along the object -X axis',
        subtype = 'FACTOR',
        min=0.0, max=1.0, default=1.0, precision=3
    )

    triplanar_show_pos_y : FloatProperty(
        name = 'Show +Y',
        description = 'Show triplanar projection on faces pointing along the object +Y axis',
        subtype = 'FACTOR',
        min=0.0, max=1.0, default=1.0, precision=3
    )

    triplanar_show_neg_y : FloatProperty(
        name = 'Show -Y',
        description = 'Show triplanar projection on faces pointing along the object -Y axis',
        subtype = 'FACTOR',
        min=0.0, max=1.0, default=1.0, precision=3
    )

    triplanar_show_pos_z : FloatProperty(
        name = 'Show +Z',
        description = 'Show triplanar projection on faces pointing along the object +Z axis',
        subtype = 'FACTOR',
        min=0.0, max=1.0, default=1.0, precision=3
    )

    triplanar_show_neg_z : FloatProperty(
        name = 'Show -Z',
        description = 'Show triplanar projection on faces pointing along the object -Z axis',
        subtype = 'FACTOR',
        min=0.0, max=1.0, default=1.0, precision=3
    )
