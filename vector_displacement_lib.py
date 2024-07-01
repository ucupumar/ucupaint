import bpy
from .common import *

GEO_TANGENT2OBJECT = '~yPL GEO Tangent2Object'
GEO_VDM_LOADER = '~yPL GEO VDM Loader'
MAT_OFFSET_TANGENT_SPACE = '~yPL MAT Tangent Space Offset'
MAT_TANGENT_BAKE = '~yPL MAT Tangent Bake'
MAT_BITANGENT_BAKE = '~yPL MAT Bitangent Bake'
SHA_PACK_VECTOR = '~yPL SHA Pack Vector'
SHA_OBJECT2TANGENT = '~yPL SHA Object2Tangent'
SHA_BITANGENT_CALC = '~yPL SHA Bitangent Calculation'

OFFSET_ATTR = 'yP Sculpt Offset'
BSIGN_ATTR = 'yP Bitangent Sign'

def create_link(tree, out, inp):
    if not any(l for l in out.links if l.to_socket == inp):
        tree.links.new(out, inp)
        #print(out, 'is connected to', inp)
    if inp.node: return inp.node.outputs
    return None

def get_tangent_bake_mat(uv_name='', target_image=None):
    mat = bpy.data.materials.get(MAT_TANGENT_BAKE)
    if not mat:
        mat = bpy.data.materials.new(MAT_TANGENT_BAKE)
        mat.use_nodes = True

        tree = mat.node_tree
        nodes = tree.nodes
        links = tree.links

        # Remove principled
        prin = [n for n in nodes if n.type == 'BSDF_PRINCIPLED']
        if prin: nodes.remove(prin[0])

        # Create nodes
        emission = nodes.new('ShaderNodeEmission')
        emission.name = emission.label = 'Emission'

        tangent = nodes.new('ShaderNodeTangent')
        tangent.name = tangent.label = 'Tangent'
        tangent.direction_type = 'UV_MAP'

        transform = nodes.new('ShaderNodeVectorTransform')
        transform.name = transform.label = 'World to Object'
        transform.vector_type = 'VECTOR'
        transform.convert_from = 'WORLD'
        transform.convert_to = 'OBJECT'

        bake_target = nodes.new('ShaderNodeTexImage')
        bake_target.name = bake_target.label = 'Bake Target'
        nodes.active = bake_target

        end = nodes.get('Material Output')

        # Node Arrangements
        loc = Vector((0, 0))

        tangent.location = loc
        loc.y -= 200

        bake_target.location = loc

        loc.y = 0
        loc.x += 200

        transform.location = loc
        loc.x += 200

        emission.location = loc
        loc.x += 200

        end.location = loc

        # Node Connections
        links.new(tangent.outputs[0], transform.inputs[0])
        links.new(transform.outputs[0], emission.inputs[0])
        links.new(emission.outputs[0], end.inputs[0])

        # Info nodes
        create_info_nodes(tree)

    bake_target = mat.node_tree.nodes.get('Bake Target')
    bake_target.image = target_image

    tangent = mat.node_tree.nodes.get('Tangent')
    tangent.uv_map = uv_name

    return mat

def get_bitangent_bake_mat(uv_name='', target_image=None):
    mat = bpy.data.materials.get(MAT_BITANGENT_BAKE)
    if not mat:
        mat = bpy.data.materials.new(MAT_BITANGENT_BAKE)
        mat.use_nodes = True

        tree = mat.node_tree
        nodes = tree.nodes
        links = tree.links

        # Remove principled
        prin = [n for n in nodes if n.type == 'BSDF_PRINCIPLED']
        if prin: nodes.remove(prin[0])

        # Create nodes
        emission = nodes.new('ShaderNodeEmission')
        emission.name = emission.label = 'Emission'

        tangent = nodes.new('ShaderNodeTangent')
        tangent.name = tangent.label = 'Tangent'
        tangent.direction_type = 'UV_MAP'

        tangent_transform = nodes.new('ShaderNodeVectorTransform')
        tangent_transform.name = tangent_transform.label = 'Tangent World to Object'
        tangent_transform.vector_type = 'VECTOR'
        tangent_transform.convert_from = 'WORLD'
        tangent_transform.convert_to = 'OBJECT'

        bsign = nodes.new('ShaderNodeAttribute')
        bsign.attribute_name = BSIGN_ATTR
        bsign.name = bsign.label = 'Bitangent Sign'

        bcalc = nodes.new('ShaderNodeGroup')
        bcalc.node_tree = get_bitangent_calc_shader_tree()
        bcalc.name = bcalc.label = 'Bitangent Calculation'

        bake_target = nodes.new('ShaderNodeTexImage')
        bake_target.name = bake_target.label = 'Bake Target'
        nodes.active = bake_target

        end = nodes.get('Material Output')

        # Node Arrangements
        loc = Vector((0, 0))

        bcalc.location = loc
        loc.y -= 200

        bsign.location = loc
        loc.y -= 200

        tangent_transform.location = loc
        loc.y -= 200

        tangent.location = loc
        loc.y -= 200

        loc.y = 0
        loc.x += 200

        emission.location = loc
        loc.y -= 200

        bake_target.location = loc

        loc.y = 0
        loc.x += 200

        end.location = loc

        # Node Connections
        links.new(tangent.outputs[0], tangent_transform.inputs[0])
        links.new(tangent_transform.outputs[0], bcalc.inputs['Tangent'])
        links.new(bsign.outputs['Fac'], bcalc.inputs['Bitangent Sign'])
        links.new(bcalc.outputs[0], emission.inputs[0])
        links.new(emission.outputs[0], end.inputs[0])

        # Info nodes
        create_info_nodes(tree)

    bake_target = mat.node_tree.nodes.get('Bake Target')
    bake_target.image = target_image

    tangent = mat.node_tree.nodes.get('Tangent')
    tangent.uv_map = uv_name

    return mat

def get_bitangent_calc_shader_tree():
    tree = bpy.data.node_groups.get(SHA_BITANGENT_CALC)
    if not tree:
        tree = bpy.data.node_groups.new(SHA_BITANGENT_CALC, 'ShaderNodeTree')
        nodes = tree.nodes
        links = tree.links

        create_essential_nodes(tree)
        start = nodes.get(TREE_START)
        end = nodes.get(TREE_END)

        # Create IO
        new_tree_input(tree, 'Tangent', 'NodeSocketVector')
        new_tree_input(tree, 'Bitangent Sign', 'NodeSocketFloat')
        new_tree_output(tree, 'Bitangent', 'NodeSocketVector')

        # Create nodes
        geom = nodes.new('ShaderNodeNewGeometry')
        cross = nodes.new('ShaderNodeVectorMath')
        cross.operation = 'CROSS_PRODUCT'
        normalize = nodes.new('ShaderNodeVectorMath')
        normalize.operation = 'NORMALIZE'
        transform = nodes.new('ShaderNodeVectorTransform')
        transform.vector_type = 'VECTOR'
        transform.convert_from = 'WORLD'
        transform.convert_to = 'OBJECT'

        # Bitangent sign nodes
        bit_mul = nodes.new('ShaderNodeMath')
        bit_mul.operation = 'MULTIPLY'
        bit_mul.inputs[1].default_value = -1.0

        bit_mix = nodes.new('ShaderNodeMixRGB')

        final_mul = nodes.new('ShaderNodeVectorMath')
        final_mul.operation = 'MULTIPLY'

        # Node Arrangements
        loc = Vector((0, 0))

        start.location = loc
        loc.y -= 200
        transform.location = loc
        loc.y -= 200
        geom.location = loc

        loc.y = 0
        loc.x += 200

        cross.location = loc
        loc.y -= 200
        bit_mul.location = loc
        loc.y -= 200

        loc.y = 0
        loc.x += 200

        normalize.location = loc
        loc.y -= 200
        bit_mix.location = loc
        loc.y -= 200

        loc.y = 0
        loc.x += 200

        final_mul.location = loc

        loc.x += 200

        end.location = loc

        # Node connection
        links.new(geom.outputs['Normal'], transform.inputs[0])
        links.new(transform.outputs[0], cross.inputs[0])
        links.new(start.outputs['Tangent'], cross.inputs[1])

        links.new(cross.outputs[0], normalize.inputs[0])

        links.new(start.outputs['Bitangent Sign'], bit_mul.inputs[0])
        links.new(geom.outputs['Backfacing'], bit_mix.inputs[0])
        links.new(start.outputs['Bitangent Sign'], bit_mix.inputs[1])
        links.new(bit_mul.outputs[0], bit_mix.inputs[2])

        links.new(normalize.outputs[0], final_mul.inputs[0])
        links.new(bit_mix.outputs[0], final_mul.inputs[1])

        links.new(final_mul.outputs[0], end.inputs[0])

        # Info nodes
        create_info_nodes(tree)

    return tree

def get_pack_vector_shader_tree():
    tree = bpy.data.node_groups.get(SHA_PACK_VECTOR)
    if not tree:
        tree = bpy.data.node_groups.new(SHA_PACK_VECTOR, 'ShaderNodeTree')
        nodes = tree.nodes
        links = tree.links

        create_essential_nodes(tree)
        start = nodes.get(TREE_START)
        end = nodes.get(TREE_END)

        # Create IO
        new_tree_input(tree, 'Vector', 'NodeSocketVector')
        new_tree_output(tree, 'Vector', 'NodeSocketVector')
        inp = new_tree_input(tree, 'Max Value', 'NodeSocketFloat')
        inp.default_value = 1.0

        # Create nodes
        divide = nodes.new('ShaderNodeVectorMath')
        divide.operation = 'DIVIDE'
        multiply = nodes.new('ShaderNodeVectorMath')
        multiply.operation = 'MULTIPLY'
        multiply.inputs[1].default_value = Vector((0.5, 0.5, 0.5))
        add = nodes.new('ShaderNodeVectorMath')
        add.operation = 'ADD'
        add.inputs[1].default_value = Vector((0.5, 0.5, 0.5))

        # Node Arrangements
        loc = Vector((0, 0))

        start.location = loc
        loc.x += 200

        divide.location = loc
        loc.x += 200

        multiply.location = loc
        loc.x += 200

        add.location = loc
        loc.x += 200

        end.location = loc

        # Node connection
        vec = start.outputs[0]
        links.new(start.outputs[1], divide.inputs[1])

        vec = create_link(tree, vec, divide.inputs[0])[0]
        vec = create_link(tree, vec, multiply.inputs[0])[0]
        vec = create_link(tree, vec, add.inputs[0])[0]
        create_link(tree, vec, end.inputs[0])

        # Info nodes
        create_info_nodes(tree)

    return tree

def get_object2tangent_shader_tree():
    tree = bpy.data.node_groups.get(SHA_OBJECT2TANGENT)
    if not tree:
        tree = bpy.data.node_groups.new(SHA_OBJECT2TANGENT, 'ShaderNodeTree')

        nodes = tree.nodes
        links = tree.links

        create_essential_nodes(tree)
        start = nodes.get(TREE_START)
        end = nodes.get(TREE_END)

        # Create IO
        new_tree_input(tree, 'Vector', 'NodeSocketVector')
        new_tree_input(tree, 'Tangent', 'NodeSocketVector')
        new_tree_input(tree, 'Bitangent', 'NodeSocketVector')
        new_tree_output(tree, 'Vector', 'NodeSocketVector')

        normal = nodes.new('ShaderNodeNewGeometry')
        transform = nodes.new('ShaderNodeVectorTransform')
        transform.vector_type = 'VECTOR'
        transform.convert_from = 'WORLD'
        transform.convert_to = 'OBJECT'

        # Dot product nodes
        dottangent = nodes.new('ShaderNodeVectorMath')
        dottangent.operation = 'DOT_PRODUCT'
        dotbitangent = nodes.new('ShaderNodeVectorMath')
        dotbitangent.operation = 'DOT_PRODUCT'
        dotnormal = nodes.new('ShaderNodeVectorMath')
        dotnormal.operation = 'DOT_PRODUCT'

        finalvec = nodes.new('ShaderNodeCombineXYZ')

        # Node Arrangements
        loc = Vector((0, 0))

        start.location = loc
        loc.y -= 200
        transform.location = loc
        loc.y -= 200
        normal.location = loc

        loc.y = 0
        loc.x += 200

        dottangent.location = loc
        loc.y -= 200
        dotbitangent.location = loc
        loc.y -= 200
        dotnormal.location = loc

        loc.y = 0
        loc.x += 200

        finalvec.location = loc

        loc.x += 200

        end.location = loc

        # Node Connection

        links.new(start.outputs['Vector'], dottangent.inputs[0])
        links.new(start.outputs['Vector'], dotbitangent.inputs[0])
        links.new(start.outputs['Vector'], dotnormal.inputs[0])

        links.new(start.outputs['Tangent'], dottangent.inputs[1])
        links.new(start.outputs['Bitangent'], dotbitangent.inputs[1])
        links.new(normal.outputs['Normal'], transform.inputs[0])
        links.new(transform.outputs[0], dotnormal.inputs[1])

        links.new(dottangent.outputs['Value'], finalvec.inputs[0])
        links.new(dotbitangent.outputs['Value'], finalvec.inputs[1])
        links.new(dotnormal.outputs['Value'], finalvec.inputs[2])

        links.new(finalvec.outputs[0], end.inputs[0])

        # Info nodes
        create_info_nodes(tree)

    return tree

def get_offset_bake_mat(uv_name='', target_image=None, bitangent_image=None):
    mat = bpy.data.materials.get(MAT_OFFSET_TANGENT_SPACE)
    if not mat:
        mat = bpy.data.materials.new(MAT_OFFSET_TANGENT_SPACE)
        mat.use_nodes = True

        tree = mat.node_tree
        nodes = tree.nodes
        links = tree.links

        # Remove principled
        prin = [n for n in nodes if n.type == 'BSDF_PRINCIPLED']
        if prin: nodes.remove(prin[0])

        # Create nodes
        emission = nodes.new('ShaderNodeEmission')
        emission.name = emission.label = 'Emission'

        tangent = nodes.new('ShaderNodeTangent')
        tangent.direction_type = 'UV_MAP'
        tangent.name = tangent.label = 'Tangent'

        tangent_transform = nodes.new('ShaderNodeVectorTransform')
        tangent_transform.vector_type = 'VECTOR'
        tangent_transform.convert_from = 'WORLD'
        tangent_transform.convert_to = 'OBJECT'
        tangent_transform.name = tangent_transform.label = 'Tangent Transform'

        offset = nodes.new('ShaderNodeAttribute')
        offset.attribute_name = OFFSET_ATTR
        offset.name = offset.label = 'Offset'

        # For baked bitangent
        bitangent = nodes.new('ShaderNodeTexImage')
        bitangent.name = bitangent.label = 'Bitangent'
        bitangent.image = bitangent_image
        bitangent_uv = nodes.new('ShaderNodeUVMap')
        bitangent_uv.name = bitangent_uv.label = 'Bitangent UV'

        object2tangent = nodes.new('ShaderNodeGroup')
        object2tangent.node_tree = get_object2tangent_shader_tree()
        object2tangent.name = object2tangent.label = 'Object to Tangent'

        pack_vector = nodes.new('ShaderNodeGroup')
        pack_vector.node_tree = get_pack_vector_shader_tree()
        pack_vector.name = pack_vector.label = 'Pack Vector'
        pack_vector.mute = True
        
        bake_target = nodes.new('ShaderNodeTexImage')
        bake_target.name = bake_target.label = 'Bake Target'
        nodes.active = bake_target

        end = nodes.get('Material Output')

        # Node Arrangements
        loc = Vector((0, 0))

        offset.location = loc
        loc.y -= 200

        tangent_transform.location = loc
        loc.y -= 200

        tangent.location = loc
        loc.y -= 200

        bitangent.location = loc
        loc.y -= 200

        bitangent_uv.location = loc
        loc.y -= 200

        loc.y = 0
        loc.x += 200

        object2tangent.location = loc

        loc.y = 0
        loc.x += 200

        pack_vector.location = loc

        loc.y = 0
        loc.x += 200

        emission.location = loc
        loc.y -= 200

        bake_target.location = loc

        loc.y = 0
        loc.x += 200

        end.location = loc

        # Node Connections
        links.new(offset.outputs['Vector'], object2tangent.inputs['Vector'])
        links.new(tangent.outputs['Tangent'], tangent_transform.inputs[0])
        links.new(tangent_transform.outputs[0], object2tangent.inputs['Tangent'])
        links.new(bitangent_uv.outputs[0], bitangent.inputs['Vector'])
        links.new(bitangent.outputs[0], object2tangent.inputs['Bitangent'])

        links.new(object2tangent.outputs['Vector'], pack_vector.inputs['Vector'])
        links.new(pack_vector.outputs['Vector'], emission.inputs[0])
        links.new(emission.outputs[0], end.inputs[0])

        # Info nodes
        #create_info_nodes(tree)

    tangent = mat.node_tree.nodes.get('Tangent')
    tangent.uv_map = uv_name

    bitangent_uv = mat.node_tree.nodes.get('Bitangent UV')
    bitangent_uv.uv_map = uv_name

    bake_target = mat.node_tree.nodes.get('Bake Target')
    bake_target.image = target_image

    bitangent = mat.node_tree.nodes.get('Bitangent')
    bitangent.image = bitangent_image

    return mat

def get_tangent2object_geo_tree():

    tree = bpy.data.node_groups.get(GEO_TANGENT2OBJECT)
    if not tree:
        tree = bpy.data.node_groups.new(GEO_TANGENT2OBJECT, 'GeometryNodeTree')
        nodes = tree.nodes
        links = tree.links

        create_essential_nodes(tree)
        start = nodes.get(TREE_START)
        end = nodes.get(TREE_END)

        # Create IO
        new_tree_input(tree, 'Vector', 'NodeSocketVector')
        new_tree_input(tree, 'Tangent', 'NodeSocketVector')
        new_tree_input(tree, 'Bitangent', 'NodeSocketVector')
        new_tree_output(tree, 'Vector', 'NodeSocketVector')

        normal = nodes.new('GeometryNodeInputNormal')

        # Matrix nodes
        septangent = nodes.new('ShaderNodeSeparateXYZ')
        sepbitangent = nodes.new('ShaderNodeSeparateXYZ')
        sepnormal = nodes.new('ShaderNodeSeparateXYZ')

        comtangent = nodes.new('ShaderNodeCombineXYZ')
        combitangent = nodes.new('ShaderNodeCombineXYZ')
        comnormal = nodes.new('ShaderNodeCombineXYZ')

        # Dot product nodes
        dottangent = nodes.new('ShaderNodeVectorMath')
        dottangent.operation = 'DOT_PRODUCT'
        dotbitangent = nodes.new('ShaderNodeVectorMath')
        dotbitangent.operation = 'DOT_PRODUCT'
        dotnormal = nodes.new('ShaderNodeVectorMath')
        dotnormal.operation = 'DOT_PRODUCT'

        finalvec = nodes.new('ShaderNodeCombineXYZ')

        # Node Arrangements
        loc = Vector((0, 0))

        start.location = loc
        loc.y -= 200
        normal.location = loc

        loc.y = 0
        loc.x += 200

        septangent.location = loc
        loc.y -= 200
        sepbitangent.location = loc
        loc.y -= 200
        sepnormal.location = loc

        loc.y = 0
        loc.x += 200

        comtangent.location = loc
        loc.y -= 200
        combitangent.location = loc
        loc.y -= 200
        comnormal.location = loc

        loc.y = 0
        loc.x += 200

        dottangent.location = loc
        loc.y -= 200
        dotbitangent.location = loc
        loc.y -= 200
        dotnormal.location = loc

        loc.y = 0
        loc.x += 200

        finalvec.location = loc

        loc.x += 200

        end.location = loc

        # Node Connection

        links.new(start.outputs['Tangent'], septangent.inputs[0])
        links.new(start.outputs['Bitangent'], sepbitangent.inputs[0])
        links.new(normal.outputs['Normal'], sepnormal.inputs[0])

        links.new(septangent.outputs[0], comtangent.inputs[0])
        links.new(septangent.outputs[1], combitangent.inputs[0])
        links.new(septangent.outputs[2], comnormal.inputs[0])

        links.new(sepbitangent.outputs[0], comtangent.inputs[1])
        links.new(sepbitangent.outputs[1], combitangent.inputs[1])
        links.new(sepbitangent.outputs[2], comnormal.inputs[1])

        links.new(sepnormal.outputs[0], comtangent.inputs[2])
        links.new(sepnormal.outputs[1], combitangent.inputs[2])
        links.new(sepnormal.outputs[2], comnormal.inputs[2])

        links.new(comtangent.outputs[0], dottangent.inputs[0])
        links.new(combitangent.outputs[0], dotbitangent.inputs[0])
        links.new(comnormal.outputs[0], dotnormal.inputs[0])

        links.new(start.outputs['Vector'], dottangent.inputs[1])
        links.new(start.outputs['Vector'], dotbitangent.inputs[1])
        links.new(start.outputs['Vector'], dotnormal.inputs[1])

        links.new(dottangent.outputs['Value'], finalvec.inputs[0])
        links.new(dotbitangent.outputs['Value'], finalvec.inputs[1])
        links.new(dotnormal.outputs['Value'], finalvec.inputs[2])

        links.new(finalvec.outputs[0], end.inputs[0])

        # Info nodes
        #create_info_nodes(tree)

    return tree

def get_vdm_loader_geotree(uv_name='', vdm_image=None, tangent_image=None, bitangent_image=None, intensity=1.0):
    tree = bpy.data.node_groups.get(GEO_VDM_LOADER)

    if not tree:
        tree = bpy.data.node_groups.new(GEO_VDM_LOADER, 'GeometryNodeTree')
        nodes = tree.nodes
        links = tree.links

        create_essential_nodes(tree)
        start = nodes.get(TREE_START)
        end = nodes.get(TREE_END)

        # Create IO
        new_tree_input(tree, 'Geometry', 'NodeSocketGeometry')
        new_tree_output(tree, 'Geometry', 'NodeSocketGeometry')

        # Create nodes
        vdm = tree.nodes.new('GeometryNodeImageTexture')
        vdm.label = 'VDM'
        vdm.inputs[0].default_value = vdm_image

        tangent = tree.nodes.new('GeometryNodeImageTexture')
        tangent.label = 'Tangent'
        tangent.inputs[0].default_value = tangent_image

        bitangent = tree.nodes.new('GeometryNodeImageTexture')
        bitangent.label = 'Bitangent'
        bitangent.inputs[0].default_value = bitangent_image

        uv_map = tree.nodes.new('GeometryNodeInputNamedAttribute')
        uv_map.label = 'UV Map'
        uv_map.data_type = 'FLOAT_VECTOR'
        uv_map.inputs[0].default_value = uv_name  

        tangent2object = tree.nodes.new('GeometryNodeGroup')
        tangent2object.node_tree = get_tangent2object_geo_tree()

        intensity_multiplier = tree.nodes.new('ShaderNodeVectorMath')
        intensity_multiplier.operation = 'MULTIPLY'
        intensity_multiplier.inputs[1].default_value = (intensity, intensity, intensity)

        offset_capture = tree.nodes.new('GeometryNodeCaptureAttribute')
        offset_capture.label = 'Offset Capture'
        offset_capture.domain = 'CORNER'

        # Capture items is manually defined in Blender 4.2
        if is_greater_than_420():
            offset_capture.capture_items.new('VECTOR', 'Vector')
        else: offset_capture.data_type = 'FLOAT_VECTOR'

        offset = tree.nodes.new('GeometryNodeSetPosition')
        offset.label = 'Offset'

        # Node Arrangements
        loc = Vector((0, 0))
        
        start.location = loc
        loc.y -= 100

        vdm.location = loc
        loc.y -= 200

        tangent.location = loc
        loc.y -= 200

        bitangent.location = loc
        loc.y -= 200

        uv_map.location = loc
        loc.y = 0
        loc.x += 300

        tangent2object.location = loc
        loc.x += 200

        intensity_multiplier.location = loc
        loc.x += 200

        offset_capture.location = loc
        loc.x += 200

        offset.location = loc
        loc.x += 200

        end.location = loc

        # Node Connection

        links.new(uv_map.outputs[0], vdm.inputs[1])
        links.new(uv_map.outputs[0], tangent.inputs[1])
        links.new(uv_map.outputs[0], bitangent.inputs[1])

        links.new(vdm.outputs[0], tangent2object.inputs[0])
        links.new(tangent.outputs[0], tangent2object.inputs[1])
        links.new(bitangent.outputs[0], tangent2object.inputs[2])

        links.new(tangent2object.outputs[0], intensity_multiplier.inputs[0])

        links.new(start.outputs[0], offset_capture.inputs[0])
        #links.new(tangent2object.outputs[0], offset_capture.inputs[1])
        links.new(intensity_multiplier.outputs[0], offset_capture.inputs[1])

        links.new(offset_capture.outputs[0], offset.inputs[0])
        links.new(offset_capture.outputs[1], offset.inputs[3])

        #links.new(start.outputs[0], offset.inputs[0])
        links.new(offset.outputs[0], end.inputs[0])

        # Info nodes
        #create_info_nodes(tree)

    return tree
