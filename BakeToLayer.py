import bpy, re, time, math
from bpy.props import *
from mathutils import *
from .common import *
from .bake_common import *
from .subtree import *
from .node_connections import *
from .node_arrangements import *
from . import lib, Layer, Mask, ImageAtlas, Modifier, MaskModifier

bake_type_items = (
        ('AO', 'Ambient Occlusion', ''),
        ('POINTINESS', 'Pointiness', ''),
        ('CAVITY', 'Cavity', ''),
        ('DUST', 'Dust', ''),
        ('PAINT_BASE', 'Paint Base', ''),
        ('BEVEL_NORMAL', 'Bevel Normal', ''),
        ('BEVEL_MASK', 'Bevel Grayscale', ''),
        )

TEMP_VCOL = '__temp__vcol__'

class YBakeToLayer(bpy.types.Operator):
    bl_idname = "node.y_bake_to_layer"
    bl_label = "Bake To Layer"
    bl_description = "Bake something as layer/mask"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(default='')

    uv_map = StringProperty(default='')
    uv_map_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    overwrite = BoolProperty(
            name='Overwrite available layer',
            description='Overwrite available layer',
            default=False
            )
    overwrite_name = StringProperty(default='')
    overwrite_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    samples = IntProperty(name='Bake Samples', 
            description='Bake Samples, more means less jagged on generated textures', 
            default=1, min=1)

    margin = IntProperty(name='Bake Margin',
            description = 'Bake margin in pixels',
            default=5, subtype='PIXEL')

    type = EnumProperty(
            name = 'Bake Type',
            description = 'Bake Type',
            items = bake_type_items,
            default='AO'
            )

    # AO Props
    ao_distance = FloatProperty(default=1.0)

    # Bevel Props
    bevel_samples = IntProperty(default=4, min=2, max=16)
    bevel_radius = FloatProperty(default=0.05, min=0.0, max=1000.0)

    target_type = EnumProperty(
            name = 'Target Bake Type',
            description = 'Target Bake Type',
            items = (('LAYER', 'Layer', ''),
                     ('MASK', 'Mask', '')),
            default='LAYER'
            )

    fxaa = BoolProperty(name='Use FXAA', 
            description = "Use FXAA to baked image (doesn't work with float images)",
            default=False)

    width = IntProperty(name='Width', default = 1024, min=1, max=4096)
    height = IntProperty(name='Height', default = 1024, min=1, max=4096)

    channel_idx = EnumProperty(
            name = 'Channel',
            description = 'Channel of new layer, can be changed later',
            items = Layer.channel_items)
            #update=Layer.update_channel_idx_new_layer)

    blend_type = EnumProperty(
        name = 'Blend',
        items = blend_type_items,
        default = 'MIX')

    normal_blend_type = EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'MIX')

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this layer',
            items = Layer.get_normal_map_type_items)
            #default = 'NORMAL_MAP')

    hdr = BoolProperty(name='32 bit Float', default=True)

    use_baked_disp = BoolProperty(
            name='Use Baked Displacement Map',
            description='Use baked displacement map, this will also apply subdiv setup on object',
            default=False
            )

    flip_normals = BoolProperty(
            name='Flip Normals',
            description='Flip normal of mesh',
            default=False
            )

    only_local = BoolProperty(
            name='Only Local',
            description='Only bake local ambient occlusion',
            default=False
            )

    subsurf_influence = BoolProperty(
            name='Subsurf Influence',
            description='Take account subsurf when baking cavity',
            default=False
            )

    force_bake_all_polygons = BoolProperty(
            name='Force Bake all Polygons',
            description='Force bake all polygons, useful if material is not using direct polygon (ex: solidify material)',
            default=False)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def invoke(self, context, event):
        obj = self.obj = context.object
        scene = self.scene = context.scene
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        # Default normal map type is bump
        self.normal_map_type = 'BUMP_MAP'

        # Default FXAA is on
        #self.fxaa = True

        # Default samples is 1
        self.samples = 1

        # Set channel to first one, just in case
        self.channel_idx = str(0)

        # Set name
        mat = get_active_material()
        if self.type == 'AO':
            self.blend_type = 'MULTIPLY'
            suffix = 'AO'
            self.samples = 32
        elif self.type == 'POINTINESS':
            self.blend_type = 'ADD'
            suffix = 'Pointiness'
            self.fxaa = False
        elif self.type == 'CAVITY':
            self.blend_type = 'MIX'
            suffix = 'Cavity'
        elif self.type == 'DUST':
            self.blend_type = 'MIX'
            suffix = 'Dust'
        elif self.type == 'PAINT_BASE':
            self.blend_type = 'MIX'
            suffix = 'Paint Base'
        elif self.type == 'BEVEL_NORMAL':
            self.blend_type = 'MIX'
            self.normal_blend_type = 'OVERLAY'
            suffix = 'Bevel Normal'
            self.samples = 32

            height_root_ch = get_root_height_channel(yp)
            if height_root_ch:
                self.channel_idx = str(get_channel_index(height_root_ch))

            self.normal_map_type = 'NORMAL_MAP'

        elif self.type == 'BEVEL_MASK':
            self.blend_type = 'MIX'
            suffix = 'Bevel Grayscale'
            self.samples = 32

        self.name = get_unique_name(mat.name + ' ' + suffix, bpy.data.images)

        # Clear overwrite_coll
        self.overwrite_coll.clear()

        # Get overwritable layers
        if self.target_type == 'LAYER':
            for layer in yp.layers:
                if layer.type == 'IMAGE':
                    source = get_layer_source(layer)
                    if source.image and suffix in source.image.name:
                        self.overwrite_coll.add().name = source.image.name

        # Get overwritable masks
        elif len(yp.layers) > 0:
            active_layer = yp.layers[yp.active_layer_index]
            for mask in active_layer.masks:
                if mask.type == 'IMAGE':
                    source = get_mask_source(mask)
                    if source.image and suffix in source.image.name:
                        self.overwrite_coll.add().name = source.image.name

        if len(self.overwrite_coll) > 0:

            self.overwrite = True
            self.overwrite_name = self.overwrite_coll[0].name
            if self.target_type == 'LAYER':
                overwrite_entity = yp.layers.get(self.overwrite_coll[0].name)
            else: 
                active_layer = yp.layers[yp.active_layer_index]
                overwrite_entity = active_layer.masks.get(self.overwrite_coll[0].name)

            if overwrite_entity:
                self.uv_map = overwrite_entity.uv_name
                if self.target_type == 'LAYER':
                    source = get_layer_source(overwrite_entity)
                else: source = get_mask_source(overwrite_entity)
                if overwrite_entity.type == 'IMAGE' and source.image:
                    if not source.image.yia.is_image_atlas:
                        self.width = source.image.size[0]
                        self.height = source.image.size[1]
                        self.hdr = source.image.is_float
                    else:
                        pass # TODO

                # Fill settings using bake info stored on image
                if source.image and source.image.y_bake_info.is_baked:
                    for attr in dir(source.image.y_bake_info):
                        if attr in dir(self):
                            try: setattr(self, attr, getattr(source.image.y_bake_info, attr))
                            except: pass
        else:
            self.overwrite = False
        
        # Use active uv layer name by default
        uv_layers = get_uv_layers(obj)

        # UV Map collections update
        self.uv_map_coll.clear()
        for uv in uv_layers:
            if not uv.name.startswith(TEMP_UV):
                self.uv_map_coll.add().name = uv.name

        #if len(uv_layers) > 0:
            #active_name = uv_layers.active.name
            #if active_name == TEMP_UV:
            #    self.uv_map = yp.layers[yp.active_layer_index].uv_name
            #else: self.uv_map = uv_layers.active.name
        if len(self.uv_map_coll) > 0 and len(self.overwrite_coll) == 0:
            self.uv_map = self.uv_map_coll[0].name

        # Set default float image
        if self.type == 'POINTINESS':
            self.hdr = True
        else:
            self.hdr = False

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        return True

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        channel = yp.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        height_root_ch = get_root_height_channel(yp)

        if is_greater_than_280():
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)

        col = row.column(align=False)

        if len(self.overwrite_coll) > 0:
            col.label(text='Overwrite:')
        if len(self.overwrite_coll) > 0 and self.overwrite:
            if self.target_type == 'LAYER':
                col.label(text='Overwrite Layer:')
            else:
                col.label(text='Overwrite Mask:')
        else:
            col.label(text='Name:')

            if self.target_type == 'LAYER':
                col.label(text='Channel:')
                if channel and channel.type == 'NORMAL':
                    col.label(text='Type:')

        if self.type == 'AO':
            col.label(text='AO Distance:')
            col.label(text='')
        elif self.type == 'CAVITY':
            col.label(text='')
        elif self.type in {'BEVEL_NORMAL', 'BEVEL_MASK'}:
            col.label(text='Bevel Samples:')
            col.label(text='Bevel Radius:')

        col.label(text='')
        col.label(text='Width:')
        col.label(text='Height:')
        col.label(text='UV Map:')
        col.label(text='Samples:')
        col.label(text='Margin:')
        col.label(text='')
        col.label(text='')

        if height_root_ch:
            col.label(text='')

        col.label(text='')

        col = row.column(align=False)

        if len(self.overwrite_coll) > 0:
            col.prop(self, 'overwrite', text='')

        if len(self.overwrite_coll) > 0 and self.overwrite:
            col.prop_search(self, "overwrite_name", self, "overwrite_coll", text='', icon='IMAGE_DATA')
        else:
            col.prop(self, 'name', text='')

            if self.target_type == 'LAYER':
                rrow = col.row(align=True)
                rrow.prop(self, 'channel_idx', text='')
                if channel:
                    if channel.type == 'NORMAL':
                        rrow.prop(self, 'normal_blend_type', text='')
                        col.prop(self, 'normal_map_type', text='')
                    else: 
                        rrow.prop(self, 'blend_type', text='')

        if self.type == 'AO':
            col.prop(self, 'ao_distance', text='')
            col.prop(self, 'only_local')
        elif self.type == 'CAVITY':
            col.prop(self, 'subsurf_influence')
        elif self.type in {'BEVEL_NORMAL', 'BEVEL_MASK'}:
            col.prop(self, 'bevel_samples', text='')
            col.prop(self, 'bevel_radius', text='')

        col.prop(self, 'hdr')
        col.prop(self, 'width', text='')
        col.prop(self, 'height', text='')
        col.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')
        col.prop(self, 'samples', text='')
        col.prop(self, 'margin', text='')
        col.prop(self, 'fxaa')
        col.prop(self, 'flip_normals')

        if height_root_ch:
            col.prop(self, 'use_baked_disp')

        col.prop(self, 'force_bake_all_polygons')

    def execute(self, context):
        mat = get_active_material()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        tree = node.node_tree
        ypui = context.window_manager.ypui

        active_layer = None
        if len(yp.layers) > 0:
            active_layer = yp.layers[yp.active_layer_index]

        if self.target_type == 'MASK' and not active_layer:
            self.report({'ERROR'}, "Mask need active layer!")
            return {'CANCELLED'}

        if self.overwrite and self.overwrite_name == '':
            self.report({'ERROR'}, "Overwrite layer/mask cannot be empty!")
            return {'CANCELLED'}

        if self.type in {'BEVEL_NORMAL', 'BEVEL_MASK'} and not is_greater_than_280():
            self.report({'ERROR'}, "Blender 2.80+ is needed to use this feature!")
            return {'CANCELLED'}

        # Remember things
        book = remember_before_bake_(yp)

        # Get all objects using material
        objs = [context.object]
        meshes = [context.object.data]
        if mat.users > 1:
            for ob in get_scene_objects():
                if ob.type != 'MESH': continue
                for i, m in enumerate(ob.data.materials):
                    if m == mat:
                        ob.active_material_index = i
                        if ob not in objs and ob.data not in meshes:
                            objs.append(ob)
                            meshes.append(ob.data)

        # Prepare bake settings
        #if self.type == 'BEVEL_NORMAL':
        #    bake_type = 'NORMAL'
        #else: 
        bake_type = 'EMIT'
        prepare_bake_settings_(book, objs, yp, samples=self.samples, margin=self.margin, 
                uv_map=self.uv_map, bake_type=bake_type)

        # Flip normals setup
        if self.flip_normals:
            #ori_mode[obj.name] = obj.mode
            if is_greater_than_280():
                bpy.ops.object.mode_set(mode = 'EDIT')
                bpy.ops.mesh.reveal()
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.flip_normals()
                bpy.ops.object.mode_set(mode = 'OBJECT')
            else:
                for obj in objs:
                    context.scene.objects.active = obj
                    bpy.ops.object.mode_set(mode = 'EDIT')
                    bpy.ops.mesh.reveal()
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.flip_normals()
                    bpy.ops.object.mode_set(mode = 'OBJECT')

        # If use only local, hide other objects
        if self.type == 'AO' and self.only_local:
            ori_hide_renders = {}
            for o in get_scene_objects():
                if o.type == 'MESH' and o not in objs:
                    ori_hide_renders[o.name] = o.hide_render
                    o.hide_render = True

        # More setup
        ori_mods = {}
        ori_mat_ids = {}
        ori_loop_locs = {}
        ori_subsurf_props = {}
        ori_subsurf_ids = {}
        ori_subsurf_multires = {}
        ori_meshes = {}
        for obj in objs:

            # Disable few modifiers
            ori_mods[obj.name] = [m.show_render for m in obj.modifiers]
            for m in obj.modifiers:
                if m.type == 'SOLIDIFY':
                    m.show_render = False
                elif m.type == 'MIRROR':
                    m.show_render = False

            # Set vertex color for cavity
            if self.type == 'CAVITY':

                ori_subsurf_props[obj.name] = []
                ori_subsurf_ids[obj.name] = []
                ori_subsurf_multires[obj.name] = []
                
                if is_greater_than_280(): context.view_layer.objects.active = obj
                else: context.scene.object.active = obj

                subsurfs = []
                if self.subsurf_influence:
                    for i, m in enumerate(obj.modifiers):
                        # NOTE: Multires has more elaborate recovery, not supported right now
                        #if m.type in {'SUBSURF', 'MULTIRES'} and m.levels > 0:
                        if m.type in {'SUBSURF'} and m.levels > 0:
                            subsurfs.append(m)

                            # Get original modifier props
                            dicts = {}
                            for prop in dir(m):
                                try: dicts[prop] = getattr(m, prop)
                                except: pass
                            ori_subsurf_props[obj.name].append(dicts)
                            ori_subsurf_ids[obj.name].append(i)
                            ori_subsurf_multires[obj.name].append(True if m.type == 'MULTIRES' else False)

                if any(subsurfs):
                    ori_meshes[obj.name] = obj.data
                    obj.data = obj.data.copy()
                    for m in subsurfs:
                        bpy.ops.object.modifier_apply(modifier=m.name)

                try:
                    vcol = obj.data.vertex_colors.new(name=TEMP_VCOL)
                    set_obj_vertex_colors(obj, vcol.name, (1.0, 1.0, 1.0))
                    obj.data.vertex_colors.active = vcol
                except: pass

                bpy.ops.paint.vertex_color_dirt(dirt_angle=math.pi/2)
                bpy.ops.paint.vertex_color_dirt()

            ori_mat_ids[obj.name] = []
            ori_loop_locs[obj.name] = []

            if len(obj.data.materials) > 1:
                active_mat_id = [i for i, m in enumerate(obj.data.materials) if m == mat][0]

                uv_layers = get_uv_layers(obj)
                uvl = uv_layers.get(self.uv_map)

                for p in obj.data.polygons:

                    # Set uv location to (0,0) if not using current material
                    if uvl and not self.force_bake_all_polygons:
                        uv_locs = []
                        for li in p.loop_indices:
                            uv_locs.append(uvl.data[li].uv.copy())
                            if p.material_index != active_mat_id:
                                uvl.data[li].uv = Vector((0.0, 0.0))

                        ori_loop_locs[obj.name].append(uv_locs)

                    # Need to assign all polygon to active material if there are multiple materials
                    ori_mat_ids[obj.name].append(p.material_index)
                    p.material_index = active_mat_id

        # If use baked disp, need to bake normal and height map first
        height_root_ch = get_root_height_channel(yp)
        if height_root_ch and self.use_baked_disp:

            # Check if baked displacement already there
            baked_disp = tree.nodes.get(height_root_ch.baked_disp)

            if baked_disp and baked_disp.image:
                disp_width = baked_disp.image.size[0]
                disp_height = baked_disp.image.size[1]
            else:
                disp_width = 1024
                disp_height = 1024

            if yp.baked_uv_name != '':
                disp_uv = yp.baked_uv_name
            else: disp_uv = yp.uvs[0].name
            
            # Use 1 sample for baking height
            context.scene.cycles.samples = 1

            # Bake height channel
            bake_channel(disp_uv, mat, node, height_root_ch, disp_width, disp_height)

            # Set baked name
            if yp.baked_uv_name == '':
                yp.baked_uv_name = disp_uv

            # Recover original bake samples
            context.scene.cycles.samples = self.samples

            # Get subsurf modifier
            #subsurf = get_subsurf_modifier(obj)

            #subsurf_found = True
            #if not subsurf:
            #    subsurf_found = False
            #    subsurf = obj.modifiers.new('_temp_subsurf', 'SUBSURF')
            #    subsurf.render_levels = height_ch.subdiv_on_level
            #else:
            #    ori_level = subsurf.render_levels

            ## Get displace modifier
            #displace = get_displace_modifier(obj)
            #if not displace:
            #    displace = obj.modifiers.new('_temp_displace', 'DISPLACE')

            #end_max_height = tree.nodes.get(height_root_ch.end_max_height)
            #max_height = end_max_height.outputs[0].default_value

            #displace.strength = height_root_ch.subdiv_tweak * max_height
            #displace.mid_level = height_root_ch.parallax_ref_plane
            #displace.uv_layer = disp_uv

            # Set to use baked
            yp.use_baked = True
            ori_subdiv_setup = height_root_ch.enable_subdiv_setup
            ori_subdiv_adaptive = height_root_ch.subdiv_adaptive
            height_root_ch.subdiv_adaptive = False
            height_root_ch.enable_subdiv_setup = True

        #return {'FINISHED'}

        # Create bake nodes
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        bsdf = mat.node_tree.nodes.new('ShaderNodeEmission')
        normal_bake = None
        geometry = None
        vector_math = None
        vector_math_1 = None
        if self.type == 'BEVEL_NORMAL':
            #bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfDiffuse')
            normal_bake = mat.node_tree.nodes.new('ShaderNodeGroup')
            normal_bake.node_tree = get_node_tree_lib(lib.BAKE_NORMAL_ACTIVE_UV)
        elif self.type == 'BEVEL_MASK':
            geometry = mat.node_tree.nodes.new('ShaderNodeNewGeometry')
            vector_math = mat.node_tree.nodes.new('ShaderNodeVectorMath')
            vector_math.operation = 'CROSS_PRODUCT'
            if is_greater_than_281():
                vector_math_1 = mat.node_tree.nodes.new('ShaderNodeVectorMath')
                vector_math_1.operation = 'LENGTH'

        # Get output node and remember original bsdf input
        output = get_active_mat_output_node(mat.node_tree)
        ori_bsdf = output.inputs[0].links[0].from_socket

        if self.type == 'AO':
            src = mat.node_tree.nodes.new('ShaderNodeAmbientOcclusion')
            src.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)

            # Links
            if is_greater_than_280():
                src.inputs[1].default_value = self.ao_distance

                mat.node_tree.links.new(src.outputs[0], bsdf.inputs[0])
                mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])
            else:

                if context.scene.world:
                    context.scene.world.light_settings.distance = self.ao_distance

                mat.node_tree.links.new(src.outputs[0], output.inputs[0])

        elif self.type == 'POINTINESS':
            src = mat.node_tree.nodes.new('ShaderNodeNewGeometry')

            # Links
            mat.node_tree.links.new(src.outputs['Pointiness'], bsdf.inputs[0])
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

        elif self.type == 'CAVITY':
            src = mat.node_tree.nodes.new('ShaderNodeGroup')
            src.node_tree = get_node_tree_lib(lib.CAVITY)

            # Set vcol
            vcol_node = src.node_tree.nodes.get('vcol')
            vcol_node.attribute_name = TEMP_VCOL

            mat.node_tree.links.new(src.outputs[0], bsdf.inputs[0])
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

        elif self.type == 'DUST':
            src = mat.node_tree.nodes.new('ShaderNodeGroup')
            src.node_tree = get_node_tree_lib(lib.DUST)

            mat.node_tree.links.new(src.outputs[0], bsdf.inputs[0])
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

        elif self.type == 'PAINT_BASE':
            src = mat.node_tree.nodes.new('ShaderNodeGroup')
            src.node_tree = get_node_tree_lib(lib.PAINT_BASE)

            mat.node_tree.links.new(src.outputs[0], bsdf.inputs[0])
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

        elif self.type == 'BEVEL_NORMAL':
            src = mat.node_tree.nodes.new('ShaderNodeBevel')

            src.samples = self.bevel_samples
            src.inputs[0].default_value = self.bevel_radius

            #mat.node_tree.links.new(src.outputs[0], bsdf.inputs['Normal'])
            mat.node_tree.links.new(src.outputs[0], normal_bake.inputs[0])
            mat.node_tree.links.new(normal_bake.outputs[0], bsdf.inputs[0])
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

        elif self.type == 'BEVEL_MASK':
            src = mat.node_tree.nodes.new('ShaderNodeBevel')

            src.samples = self.bevel_samples
            src.inputs[0].default_value = self.bevel_radius

            mat.node_tree.links.new(geometry.outputs['Normal'], vector_math.inputs[0])
            mat.node_tree.links.new(src.outputs[0], vector_math.inputs[1])
            #mat.node_tree.links.new(src.outputs[0], bsdf.inputs['Normal'])
            if is_greater_than_281():
                mat.node_tree.links.new(vector_math.outputs[0], vector_math_1.inputs[0])
                mat.node_tree.links.new(vector_math_1.outputs[1], bsdf.inputs[0])
            else:
                mat.node_tree.links.new(vector_math.outputs[1], bsdf.inputs[0])
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

        # New target image
        image = bpy.data.images.new(name=self.name,
                width=self.width, height=self.height, alpha=True, float_buffer=self.hdr)
        if self.type == 'AO':
            image.generated_color = (1.0, 1.0, 1.0, 1.0) 
        if self.type == 'BEVEL_NORMAL':
            image.generated_color = (0.5, 0.5, 1.0, 1.0) 
        else: 
            image.generated_color = (0.73, 0.73, 0.73, 1.0)
        image.colorspace_settings.name = 'Linear'

        # Set bake info to image
        image.y_bake_info.is_baked = True
        for attr in dir(image.y_bake_info):
            if attr in dir(self):
                try: setattr(image.y_bake_info, attr, getattr(self, attr))
                except: pass

        # Set bake image
        tex.image = image
        mat.node_tree.nodes.active = tex
        #return {'FINISHED'}

        # Bake!
        bpy.ops.object.bake()

        #return {'FINISHED'}

        # FXAA doesn't work with hdr image
        if not self.hdr and self.fxaa:
            fxaa_image(image, False)

        overwrite_img = None
        if self.overwrite:
            overwrite_img = bpy.data.images.get(self.overwrite_name)

        if overwrite_img:
            replaced_layer_ids = replace_image(overwrite_img, image, yp, self.uv_map)
            if replaced_layer_ids and yp.active_layer_index not in replaced_layer_ids:
                active_id = replaced_layer_ids[0]
            else: active_id = yp.active_layer_index

            if self.target_type == 'MASK':
                # Activate mask
                for mask in yp.layers[yp.active_layer_index].masks:
                    if mask.type == 'IMAGE':
                        source = get_mask_source(mask)
                        if source.image and source.image == image:
                            mask.active_edit = True

        elif self.target_type == 'LAYER':
            yp.halt_update = True
            layer = Layer.add_new_layer(node.node_tree, image.name, 'IMAGE', int(self.channel_idx), self.blend_type, 
                    self.normal_blend_type, self.normal_map_type, 'UV', self.uv_map, image)
            yp.halt_update = False
            active_id = yp.active_layer_index
        else:
            mask = Mask.add_new_mask(active_layer, image.name, 'IMAGE', 'UV', self.uv_map, image)
            mask.active_edit = True

            rearrange_layer_nodes(active_layer)
            reconnect_layer_nodes(active_layer)

            active_id = yp.active_layer_index

        # Remove temp bake nodes
        simple_remove_node(mat.node_tree, tex)
        #simple_remove_node(mat.node_tree, srgb2lin)
        simple_remove_node(mat.node_tree, bsdf)
        simple_remove_node(mat.node_tree, src)
        if normal_bake: simple_remove_node(mat.node_tree, normal_bake)
        if geometry: simple_remove_node(mat.node_tree, geometry)
        if vector_math: simple_remove_node(mat.node_tree, vector_math)
        if vector_math_1: simple_remove_node(mat.node_tree, vector_math_1)

        # Recover original bsdf
        mat.node_tree.links.new(ori_bsdf, output.inputs[0])

        # Recover subdiv setup
        if height_root_ch and self.use_baked_disp:
            yp.use_baked = False
            height_root_ch.subdiv_adaptive = ori_subdiv_adaptive
            height_root_ch.enable_subdiv_setup = ori_subdiv_setup

        for obj in objs:
            # Recover modifiers
            for i, m in enumerate(obj.modifiers):
                if ori_mods[obj.name][i] != m.show_render:
                    m.show_render = ori_mods[obj.name][i]

            # Recover material index
            if ori_mat_ids[obj.name]:
                for i, p in enumerate(obj.data.polygons):
                    if ori_mat_ids[obj.name][i] != p.material_index:
                        p.material_index = ori_mat_ids[obj.name][i]

            if ori_loop_locs[obj.name]:

                # Get uv map
                uv_layers = get_uv_layers(obj)
                uvl = uv_layers.get(self.uv_map)

                # Recover uv locations
                if uvl:
                    for i, p in enumerate(obj.data.polygons):
                        for j, li in enumerate(p.loop_indices):
                            uvl.data[li].uv = ori_loop_locs[obj.name][i][j]

            if obj.name in ori_meshes:
                temp_mesh = obj.data
                obj.data = ori_meshes[obj.name]
                bpy.data.meshes.remove(temp_mesh)

            if obj.name in ori_subsurf_props:
                for i in range(len(ori_subsurf_props[obj.name])):

                    # Recover subsurf modifier
                    mod = obj.modifiers.new(ori_subsurf_props[obj.name][i]['name'], 
                            'MULTIRES' if ori_subsurf_multires[obj.name][i] else 'SUBSURF')

                    # Recover subsurf modifier index
                    current_idx = [j for j, m in enumerate(obj.modifiers) if m == mod][0]
                    for j in range(current_idx-ori_subsurf_ids[obj.name][i]):
                        bpy.ops.object.modifier_move_up(modifier=mod.name)

                    # Recover subsurf props
                    for prop in dir(mod):
                        try: setattr(mod, prop, ori_subsurf_props[obj.name][i][prop])
                        except: pass

            # Delete cavity vcol
            vcol = obj.data.vertex_colors.get(TEMP_VCOL)
            if vcol: obj.data.vertex_colors.remove(vcol)

        # Recover flip normals setup
        if self.flip_normals:
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.mesh.flip_normals()
            bpy.ops.mesh.select_all(action='DESELECT')
            #bpy.ops.object.mode_set(mode = ori_mode)

        # Recover hidden objects
        if self.type == 'AO' and self.only_local:
            for o in get_scene_objects():
                if o.type == 'MESH' and o not in objs and o.hide_render != ori_hide_renders[o.name]:
                    o.hide_render = ori_hide_renders[o.name]

        # Recover bake settings
        recover_bake_settings_(book, yp)

        #return {'FINISHED'}

        # Reconnect and rearrange nodes
        #reconnect_yp_layer_nodes(node.node_tree)
        reconnect_yp_nodes(node.node_tree)
        rearrange_yp_nodes(node.node_tree)

        # Refresh active index
        #if active_id != yp.active_layer_index:
        yp.active_layer_index = active_id

        if self.target_type == 'MASK':
            ypui.layer_ui.expand_masks = True
        ypui.need_update = True

        # Refresh mapping and stuff
        #yp.active_layer_index = yp.active_layer_index

        return {'FINISHED'}

class YImageBakeInfoProps(bpy.types.PropertyGroup):

    is_baked = BoolProperty(default=False)

    bake_type = EnumProperty(
            name = 'Bake Type',
            description = 'Bake Type',
            items = bake_type_items,
            default='AO'
            )

    samples = IntProperty(name='Bake Samples', 
            description='Bake Samples, more means less jagged on generated textures', 
            default=1, min=1)

    margin = IntProperty(name='Bake Margin',
            description = 'Bake margin in pixels',
            default=5, subtype='PIXEL')

    flip_normals = BoolProperty(
            name='Flip Normals',
            description='Flip normal of mesh',
            default=False
            )
    
    only_local = BoolProperty(
            name='Only Local',
            description='Only bake local ambient occlusion',
            default=False
            )

    subsurf_influence = BoolProperty(
            name='Subsurf Influence',
            description='Take account subsurf when baking cavity',
            default=False
            )
    
    force_bake_all_polygons = BoolProperty(
            name='Force Bake all Polygons',
            description='Force bake all polygons, useful if material is not using direct polygon (ex: solidify material)',
            default=False)

    fxaa = BoolProperty(name='Use FXAA', 
            description = "Use FXAA to baked image (doesn't work with float images)",
            default=False)

    # AO Props
    ao_distance = FloatProperty(default=1.0)

    # Bevel Props
    bevel_samples = IntProperty(default=4, min=2, max=16)
    bevel_radius = FloatProperty(default=0.05, min=0.0, max=1000.0)

def register():
    bpy.utils.register_class(YBakeToLayer)
    bpy.utils.register_class(YImageBakeInfoProps)

    # Props 
    bpy.types.Image.y_bake_info = PointerProperty(type=YImageBakeInfoProps)

def unregister():
    bpy.utils.unregister_class(YBakeToLayer)
    bpy.utils.unregister_class(YImageBakeInfoProps)
