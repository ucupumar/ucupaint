import bpy, re, time, math, bmesh
from bpy.props import *
from mathutils import *
from .common import *
from .bake_common import *
from .subtree import *
from .node_connections import *
from .node_arrangements import *
from . import lib, Layer, Mask, ImageAtlas, Modifier, MaskModifier, BakeInfo, UDIM

TEMP_VCOL = '__temp__vcol__'
TEMP_EMISSION = '_TEMP_EMI_'

class YTryToSelectBakedVertexSelect(bpy.types.Operator):
    bl_idname = "node.y_try_to_select_baked_vertex"
    bl_label = "Try to reselect baked selected vertex"
    bl_description = "Try to reselect baked selected vertex. It might give you wrong results if mesh number of vertex changed"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def execute(self, context):
        if not hasattr(context, 'bake_info'):
            return {'CANCELLED'}

        bi = context.bake_info

        if len(bi.selected_objects) == 0:
            return {'CANCELLED'}

        if context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')

        #mat = get_active_material()
        #objs = get_all_objects_with_same_materials(mat)
        objs = [bso.object for bso in bi.selected_objects]

        #print(objs)

        # Disable viewport hide of object layer collection
        #for o in objs:
        #    layer_cols = get_object_parent_layer_collections([], bpy.context.view_layer.layer_collection, o)
        #    for lc in layer_cols:
        #        #lc.exclude = False
        #        lc.hide_viewport = False
        #        lc.collection.hide_viewport = False
        #        #lc.collection.hide_render = False

        # Get actual selectable objects
        actual_selectable_objs = []
        for o in objs:
            if is_greater_than_280():
                layer_cols = get_object_parent_layer_collections([], bpy.context.view_layer.layer_collection, o)

                #for lc in layer_cols:
                #    print(lc.name)
                
                if layer_cols and not any([lc for lc in layer_cols if lc.exclude or lc.hide_viewport or lc.collection.hide_viewport]):
                    actual_selectable_objs.append(o)
            else:
                if not o.hide_select and in_active_279_layer(o):
                    actual_selectable_objs.append(o)

        if len(actual_selectable_objs) == 0:
            self.report({'ERROR'}, "Cannot select the object!")
            return {'CANCELLED'}

        for obj in actual_selectable_objs:
            set_object_hide(obj, False)
            set_object_select(obj, True)

        set_active_object(actual_selectable_objs[0])
        
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.reveal()
        bpy.ops.mesh.select_all(action='DESELECT')

        for bso in bi.selected_objects:
            obj = bso.object
            if obj not in actual_selectable_objs: continue

            mesh = obj.data
            bm = bmesh.from_edit_mesh(mesh)

            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            if bi.selected_face_mode:
                context.tool_settings.mesh_select_mode[0] = False
                context.tool_settings.mesh_select_mode[1] = False
                context.tool_settings.mesh_select_mode[2] = True

                for bsv in bso.selected_vertex_indices:
                    try: bm.faces[bsv.index].select = True
                    except: pass
            else:
                context.tool_settings.mesh_select_mode[0] = True
                context.tool_settings.mesh_select_mode[1] = False
                context.tool_settings.mesh_select_mode[2] = False

                for bsv in bso.selected_vertex_indices:
                    try: bm.verts[bsv.index].select = True
                    except: pass

        return {'FINISHED'}

class YRemoveBakeInfoOtherObject(bpy.types.Operator):
    bl_idname = "node.y_remove_bake_info_other_object"
    bl_label = "Remove other object info"
    bl_description = "Remove other object bake info, so it won't be automatically baked anymore if you choose to rebake"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def execute(self, context):
        if not hasattr(context, 'other_object') or not hasattr(context, 'bake_info'):
            return {'CANCELLED'}

        #if len(context.bake_info.other_objects) == 1:
        #    self.report({'ERROR'}, "Cannot delete, need at least one object!")
        #    return {'CANCELLED'}

        for i, oo in enumerate(context.bake_info.other_objects):
            if oo == context.other_object:
                context.bake_info.other_objects.remove(i)
                break

        return {'FINISHED'}

def update_bake_to_layer_uv_map(self, context):
    if not UDIM.is_udim_supported(): return

    mat = get_active_material()
    objs = get_all_objects_with_same_materials(mat)
    self.use_udim = UDIM.is_uvmap_udim(objs, self.uv_map)

class YBakeToLayer(bpy.types.Operator):
    bl_idname = "node.y_bake_to_layer"
    bl_label = "Bake To Layer"
    bl_description = "Bake something as layer/mask"
    bl_options = {'REGISTER', 'UNDO'}

    name : StringProperty(default='')

    uv_map : StringProperty(default='', update=update_bake_to_layer_uv_map)
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    uv_map_1 : StringProperty(default='')

    # For choosing overwrite entity from list
    overwrite_choice : BoolProperty(
            name='Overwrite available layer',
            description='Overwrite available layer',
            default=False
            )

    # For rebake button
    overwrite_current : BoolProperty(default=False)

    overwrite_name : StringProperty(default='')
    overwrite_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    overwrite_image_name : StringProperty(default='')
    overwrite_segment_name : StringProperty(default='')

    samples : IntProperty(name='Bake Samples', 
            description='Bake Samples, more means less jagged on generated textures', 
            default=1, min=1)

    margin : IntProperty(name='Bake Margin',
            description = 'Bake margin in pixels',
            default=5, min=0, subtype='PIXEL')

    type : EnumProperty(
            name = 'Bake Type',
            description = 'Bake Type',
            items = bake_type_items,
            default='AO'
            )

    # Other objects props
    cage_extrusion : FloatProperty(
            name = 'Cage Extrusion',
            description = 'Inflate the active object by the specified distance for baking. This helps matching to points nearer to the outside of the selected object meshes',
            default=0.2, min=0.0, max=1.0)

    max_ray_distance : FloatProperty(
            name = 'Max Ray Distance',
            description = 'The maximum ray distance for matching points between the active and selected objects. If zero, there is no limit',
            default=0.2, min=0.0, max=1.0)
    
    # AO Props
    ao_distance : FloatProperty(default=1.0)

    # Bevel Props
    bevel_samples : IntProperty(default=4, min=2, max=16)
    bevel_radius : FloatProperty(default=0.05, min=0.0, max=1000.0)

    multires_base : IntProperty(default=1, min=0, max=16)

    target_type : EnumProperty(
            name = 'Target Bake Type',
            description = 'Target Bake Type',
            items = (('LAYER', 'Layer', ''),
                     ('MASK', 'Mask', '')),
            default='LAYER'
            )

    fxaa : BoolProperty(name='Use FXAA', 
            description = "Use FXAA to baked image (doesn't work with float images)",
            default=True)

    ssaa : BoolProperty(name='Use SSAA', 
            description = "Use Supersample AA to baked image",
            default=False)

    width : IntProperty(name='Width', default = 1234, min=1, max=4096)
    height : IntProperty(name='Height', default = 1234, min=1, max=4096)

    channel_idx : EnumProperty(
            name = 'Channel',
            description = 'Channel of new layer, can be changed later',
            items = Layer.channel_items)
            #update=Layer.update_channel_idx_new_layer)

    blend_type : EnumProperty(
        name = 'Blend',
        items = blend_type_items,
        default = 'MIX')

    normal_blend_type : EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'MIX')

    normal_map_type : EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this layer',
            items = Layer.get_normal_map_type_items)
            #default = 'NORMAL_MAP')

    hdr : BoolProperty(name='32 bit Float', default=True)

    use_baked_disp : BoolProperty(
            name='Use Baked Displacement Map',
            description='Use baked displacement map, this will also apply subdiv setup on object',
            default=False
            )

    flip_normals : BoolProperty(
            name='Flip Normals',
            description='Flip normal of mesh',
            default=False
            )

    only_local : BoolProperty(
            name='Only Local',
            description='Only bake local ambient occlusion',
            default=False
            )

    subsurf_influence : BoolProperty(
            name='Subsurf / Multires Influence',
            description='Take account subsurf or multires when baking cavity',
            default=True
            )

    force_bake_all_polygons : BoolProperty(
            name='Force Bake all Polygons',
            description='Force bake all polygons, useful if material is not using direct polygon (ex: solidify material)',
            default=False)

    bake_device : EnumProperty(
            name='Bake Device',
            description='Device to use for baking',
            items = (('GPU', 'GPU Compute', ''),
                     ('CPU', 'CPU', '')),
            default='CPU'
            )

    use_image_atlas : BoolProperty(
            name = 'Use Image Atlas',
            description='Use Image Atlas',
            default=False)

    use_udim : BoolProperty(
            name = 'Use UDIM Tiles',
            description='Use UDIM Tiles',
            default=False)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def invoke(self, context, event):

        if hasattr(context, 'entity'):
            self.entity = context.entity
        else: self.entity = None

        obj = self.obj = context.object
        scene = self.scene = context.scene
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        ypup = get_user_preferences()

        # UDIM is turned off by default
        #self.use_udim = False

        # Use user preference default image size if input uses default image size
        if self.width == 1234 and self.height == 1234:
            self.width = self.height = ypup.default_new_image_size

        # Default normal map type is bump
        self.normal_map_type = 'BUMP_MAP'

        # Default FXAA is on
        #self.fxaa = True

        # Default samples is 1
        self.samples = 1

        # Set channel to first one, just in case
        if len(yp.channels) > 0:
            self.channel_idx = str(0)

        # Get height channel
        height_root_ch = get_root_height_channel(yp)

        # Set default float image
        if self.type in {'POINTINESS', 'MULTIRES_DISPLACEMENT'}:
            self.hdr = True
        else:
            self.hdr = False

        # Set name
        mat = get_active_material()
        if self.type == 'AO':
            self.blend_type = 'MULTIPLY'
            self.samples = 32

            # Check Ambient occlusion channel if available
            for i, c in enumerate(yp.channels):
                if c.name in {'Ambient Occlusion', 'AO'}:
                    self.channel_idx = str(i)
                    break

        elif self.type == 'POINTINESS':
            self.blend_type = 'ADD'
            self.fxaa = False
        elif self.type == 'CAVITY':
            self.blend_type = 'ADD'
        elif self.type == 'DUST':
            self.blend_type = 'MIX'
        elif self.type == 'PAINT_BASE':
            self.blend_type = 'MIX'
        elif self.type == 'BEVEL_NORMAL':
            self.blend_type = 'MIX'
            self.normal_blend_type = 'OVERLAY'
            self.use_baked_disp = False
            self.samples = 32

            if height_root_ch:
                self.channel_idx = str(get_channel_index(height_root_ch))
                self.normal_map_type = 'NORMAL_MAP'

        elif self.type == 'BEVEL_MASK':
            self.blend_type = 'MIX'
            self.use_baked_disp = False
            self.samples = 32

        elif self.type == 'MULTIRES_NORMAL':
            self.blend_type = 'MIX'

            if height_root_ch:
                self.channel_idx = str(get_channel_index(height_root_ch))
                self.normal_map_type = 'NORMAL_MAP'
                self.normal_blend_type = 'OVERLAY'

        elif self.type == 'MULTIRES_DISPLACEMENT':
            self.blend_type = 'MIX'

            if height_root_ch:
                self.channel_idx = str(get_channel_index(height_root_ch))
                self.normal_map_type = 'BUMP_MAP'
                self.normal_blend_type = 'OVERLAY'

        elif self.type == 'OTHER_OBJECT_EMISSION':
            self.subsurf_influence = False

        elif self.type == 'OTHER_OBJECT_NORMAL':
            self.subsurf_influence = False

            if height_root_ch:
                self.channel_idx = str(get_channel_index(height_root_ch))
                self.normal_map_type = 'NORMAL_MAP'
                self.normal_blend_type = 'OVERLAY'

        elif self.type == 'OTHER_OBJECT_CHANNELS':
            self.subsurf_influence = False
            self.use_image_atlas = False

        elif self.type == 'SELECTED_VERTICES':
            self.subsurf_influence = False
            self.use_baked_disp = False

        elif self.type == 'FLOW':
            self.blend_type = 'MIX'

            # Check flow channel if available
            for i, c in enumerate(yp.channels):
                if 'flow' in c.name.lower():
                    self.channel_idx = str(i)
                    break

        suffix = bake_type_suffixes[self.type]
        self.name = get_unique_name(mat.name + ' ' + suffix, bpy.data.images)

        self.overwrite_choice = False
        self.overwrite_name = ''
        overwrite_entity = None
        
        if self.overwrite_current:
            overwrite_entity = self.entity

        # Other object and selected vertices bake will not display overwrite choice
        elif not self.type.startswith('OTHER_OBJECT_') and self.type not in {'SELECTED_VERTICES'}:
        #else:

            # Clear overwrite_coll
            self.overwrite_coll.clear()

            # Get overwritable layers
            if self.target_type == 'LAYER':
                for layer in yp.layers:
                    if layer.type == 'IMAGE':
                        source = get_layer_source(layer)
                        if source.image:
                            img = source.image
                            if img.y_bake_info.is_baked and img.y_bake_info.bake_type == self.type:
                                self.overwrite_coll.add().name = layer.name
                            elif img.yia.is_image_atlas or img.yua.is_udim_atlas:
                                if img.yia.is_image_atlas:
                                    segment = img.yia.segments.get(layer.segment_name)
                                else: segment = img.yua.segments.get(layer.segment_name)
                                if segment and segment.bake_info.is_baked and segment.bake_info.bake_type == self.type:
                                    self.overwrite_coll.add().name = layer.name

            # Get overwritable masks
            elif len(yp.layers) > 0:
                active_layer = yp.layers[yp.active_layer_index]
                for mask in active_layer.masks:
                    if mask.type == 'IMAGE':
                        source = get_mask_source(mask)
                        if source.image:
                            img = source.image
                            if img.y_bake_info.is_baked and img.y_bake_info.bake_type == self.type:
                                self.overwrite_coll.add().name = mask.name
                            elif img.yia.is_image_atlas or img.yua.is_udim_atlas:
                                if img.yia.is_image_atlas:
                                    segment = img.yia.segments.get(mask.segment_name)
                                else: segment = img.yua.segments.get(mask.segment_name)
                                if segment and segment.bake_info.is_baked and segment.bake_info.bake_type == self.type:
                                    self.overwrite_coll.add().name = mask.name

            if len(self.overwrite_coll) > 0:

                self.overwrite_choice = True
                if self.target_type == 'LAYER':
                    overwrite_entity = yp.layers.get(self.overwrite_coll[0].name)
                else: 
                    active_layer = yp.layers[yp.active_layer_index]
                    overwrite_entity = active_layer.masks.get(self.overwrite_coll[0].name)
            else:
                self.overwrite_choice = False

        self.overwrite_image_name = ''
        self.overwrite_segment_name = ''
        if overwrite_entity:
            #self.entity = overwrite_entity
            self.uv_map = overwrite_entity.uv_name

            if self.target_type == 'LAYER':
                source = get_layer_source(overwrite_entity)
            else: source = get_mask_source(overwrite_entity)

            bi = None
            if overwrite_entity.type == 'IMAGE' and source.image:
                self.overwrite_image_name = source.image.name
                if not source.image.yia.is_image_atlas and not source.image.yua.is_udim_atlas:
                    self.overwrite_name = source.image.name
                    self.width = source.image.size[0]
                    self.height = source.image.size[1]
                    self.use_image_atlas = False
                    bi = source.image.y_bake_info
                else:
                    self.overwrite_name = overwrite_entity.name
                    self.overwrite_segment_name = overwrite_entity.segment_name
                    if source.image.yia.is_image_atlas:
                        segment = source.image.yia.segments.get(overwrite_entity.segment_name)
                        self.width = segment.width
                        self.height = segment.height
                    else: 
                        segment = source.image.yua.segments.get(overwrite_entity.segment_name)
                        tilenums = UDIM.get_udim_segment_tilenums(segment)
                        if len(tilenums) > 0:
                            tile = source.image.tiles.get(tilenums[0])
                            self.width = tile.size[0]
                            self.height = tile.size[1]
                    bi = segment.bake_info
                    self.use_image_atlas = True
                self.hdr = source.image.is_float

            # Fill settings using bake info stored on image
            if bi:
                for attr in dir(bi):
                    if attr in {'other_objects', 'selected_objects'}: continue
                    if attr.startswith('__'): continue
                    if attr.startswith('bl_'): continue
                    if attr in {'rna_type'}: continue
                    #if attr in dir(self):
                    try: setattr(self, attr, getattr(bi, attr))
                    except: pass
        
        # Use active uv layer name by default
        uv_layers = get_uv_layers(obj)

        # UV Map collections update
        self.uv_map_coll.clear()
        for uv in uv_layers:
            if not uv.name.startswith(TEMP_UV):
                self.uv_map_coll.add().name = uv.name

        if len(self.uv_map_coll) > 0 and not overwrite_entity: #len(self.overwrite_coll) == 0:
            self.uv_map = self.uv_map_coll[0].name

        if len(self.uv_map_coll) > 1:
            self.uv_map_1 = self.uv_map_coll[1].name

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        ypup = get_user_preferences()

        # New image cannot use more pixels than the image atlas
        if self.use_image_atlas:
            if self.hdr: max_size = ypup.hdr_image_atlas_size
            else: max_size = ypup.image_atlas_size
            if self.width > max_size: self.width = max_size
            if self.height > max_size: self.height = max_size

        return True

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        mat = get_active_material()

        channel = yp.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        height_root_ch = get_root_height_channel(yp)

        if is_greater_than_280():
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)

        show_subsurf_influence = not self.type.startswith('MULTIRES_') and self.type not in {'SELECTED_VERTICES'}
        show_use_baked_disp = height_root_ch and not self.type.startswith('MULTIRES_') and self.type not in {'SELECTED_VERTICES'}

        col = row.column(align=False)

        if not self.overwrite_current:

            if len(self.overwrite_coll) > 0:
                col.label(text='Overwrite:')
            if len(self.overwrite_coll) > 0 and self.overwrite_choice:
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
        else:
            col.label(text='Name:')

        if self.type.startswith('OTHER_OBJECT_'):
            col.label(text='Cage Extrusion:')
            if hasattr(bpy.context.scene.render.bake, 'max_ray_distance'):
                col.label(text='Max Ray Distance:')
        elif self.type == 'AO':
            col.label(text='AO Distance:')
            col.label(text='')
        elif self.type in {'BEVEL_NORMAL', 'BEVEL_MASK'}:
            col.label(text='Bevel Samples:')
            col.label(text='Bevel Radius:')
        elif self.type.startswith('MULTIRES_'):
            col.label(text='Base Level:')
        #elif self.type.startswith('OTHER_OBJECT_'):
        #    col.label(text='Source Object:')

        col.label(text='')
        col.label(text='Width:')
        col.label(text='Height:')
        col.label(text='UV Map:')
        if self.type == 'FLOW':
            col.label(text='Straight UV Map:')
        col.label(text='Samples:')
        col.label(text='Margin:')
        if is_greater_than_280():
            col.separator()
            col.label(text='Bake Device:')
        col.separator()
        col.label(text='')
        #col.label(text='')
        col.label(text='')

        #if not self.type.startswith('MULTIRES_'):
        if show_subsurf_influence:
            col.label(text='')

        #if height_root_ch and not self.type.startswith('MULTIRES_'):
        if show_use_baked_disp:
            col.label(text='')

        col.label(text='')
        col.label(text='')

        if self.type not in {'OTHER_OBJECT_CHANNELS'}:
            col.separator()
            col.label(text='')

        col = row.column(align=False)

        if not self.overwrite_current:
            if len(self.overwrite_coll) > 0:
                col.prop(self, 'overwrite_choice', text='')

            if len(self.overwrite_coll) > 0 and self.overwrite_choice:
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
        else:
            col.label(text=self.overwrite_name)

        if self.type.startswith('OTHER_OBJECT_'):
            col.prop(self, 'cage_extrusion', text='')
            if hasattr(bpy.context.scene.render.bake, 'max_ray_distance'):
                col.prop(self, 'max_ray_distance', text='')
        elif self.type == 'AO':
            col.prop(self, 'ao_distance', text='')
            col.prop(self, 'only_local')
        elif self.type in {'BEVEL_NORMAL', 'BEVEL_MASK'}:
            col.prop(self, 'bevel_samples', text='')
            col.prop(self, 'bevel_radius', text='')
        elif self.type.startswith('MULTIRES_'):
            col.prop(self, 'multires_base', text='')

        col.prop(self, 'hdr')
        col.prop(self, 'width', text='')
        col.prop(self, 'height', text='')
        col.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')
        if self.type == 'FLOW':
            col.prop_search(self, "uv_map_1", self, "uv_map_coll", text='', icon='GROUP_UVS')
        col.prop(self, 'samples', text='')
        col.prop(self, 'margin', text='')

        if is_greater_than_280():
            col.separator()
            col.prop(self, 'bake_device', text='')

        col.separator()
        if self.type.startswith('OTHER_OBJECT_'):
            col.prop(self, 'ssaa')
        else: col.prop(self, 'fxaa')

        col.separator()

        #if not self.type.startswith('MULTIRES_') or self.type not in {'SELECTED_VERTICES'}:
        if show_subsurf_influence:
            r = col.row()
            r.active = not self.use_baked_disp
            r.prop(self, 'subsurf_influence')

        #if height_root_ch and not self.type.startswith('MULTIRES_'):
        if show_use_baked_disp:
            col.prop(self, 'use_baked_disp')

        col.prop(self, 'flip_normals')
        col.prop(self, 'force_bake_all_polygons')

        if self.type not in {'OTHER_OBJECT_CHANNELS'}:
            col.separator()
            ccol = col.column(align=True)
            #ccol.active = not self.use_udim
            ccol.prop(self, 'use_image_atlas')

    def execute(self, context):
        T = time.time()
        mat = get_active_material()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        tree = node.node_tree
        ypui = context.window_manager.ypui
        scene = context.scene
        obj = context.object
        ypup = get_user_preferences()

        active_layer = None
        if len(yp.layers) > 0:
            active_layer = yp.layers[yp.active_layer_index]

        if self.type == 'SELECTED_VERTICES' and obj.mode != 'EDIT':
            self.report({'ERROR'}, "Should be on edit mode!")
            return {'CANCELLED'}

        if self.target_type == 'MASK' and not active_layer:
            self.report({'ERROR'}, "Mask need active layer!")
            return {'CANCELLED'}

        if (self.overwrite_choice or self.overwrite_current) and self.overwrite_name == '':
            self.report({'ERROR'}, "Overwrite layer/mask cannot be empty!")
            return {'CANCELLED'}

        if self.type in {'BEVEL_NORMAL', 'BEVEL_MASK'} and not is_greater_than_280():
            self.report({'ERROR'}, "Blender 2.80+ is needed to use this feature!")
            return {'CANCELLED'}

        if self.type in {'MULTIRES_NORMAL', 'MULTIRES_DISPLACEMENT'} and not is_greater_than_280():
            #self.report({'ERROR'}, "This feature is not implemented yet on Blender 2.79!")
            self.report({'ERROR'}, "Blender 2.80+ is needed to use this feature!")
            return {'CANCELLED'}

        if (hasattr(context.object, 'hide_viewport') and context.object.hide_viewport) or context.object.hide_render:
            self.report({'ERROR'}, "Please unhide render and viewport of active object!")
            return {'CANCELLED'}

        if self.type == 'FLOW' and (self.uv_map == '' or self.uv_map_1 == '' or self.uv_map == self.uv_map_1):
            self.report({'ERROR'}, "UVMap and Straight UVMap are cannot be the same or empty!")
            return {'CANCELLED'}

        # Get all objects using material
        if self.type.startswith('MULTIRES_') and not get_multires_modifier(context.object):
            objs = []
            meshes = []
        else:
            objs = [context.object]
            meshes = [context.object.data]

        if mat.users > 1:
            # Emptying the lists again in case active object is problematic
            objs = []
            meshes = []
            for ob in get_scene_objects():
                if ob.type != 'MESH': continue
                if hasattr(ob, 'hide_viewport') and ob.hide_viewport: continue
                if len(get_uv_layers(ob)) == 0: continue
                if self.type.startswith('MULTIRES_') and not get_multires_modifier(ob): continue
                if len(ob.data.polygons) == 0: continue

                # Do not bake objects with hide_render on
                if ob.hide_render: continue
                if not in_renderable_layer_collection(ob): continue

                for i, m in enumerate(ob.data.materials):
                    if m == mat:
                        ob.active_material_index = i
                        if ob not in objs and ob.data not in meshes:
                            objs.append(ob)
                            meshes.append(ob.data)

        if not objs:
            self.report({'ERROR'}, "No valid objects found to bake!")
            return {'CANCELLED'}

        overwrite_img = None
        if (self.overwrite_choice or self.overwrite_current) and self.overwrite_image_name != '':
            overwrite_img = bpy.data.images.get(self.overwrite_image_name)

        segment = None
        if overwrite_img:
            if overwrite_img.yia.is_image_atlas:
                segment = overwrite_img.yia.segments.get(self.overwrite_segment_name)
            elif overwrite_img.yua.is_udim_atlas:
                segment = overwrite_img.yua.segments.get(self.overwrite_segment_name)

        # Get other objects for other object baking
        other_objs = []
        
        if self.type.startswith('OTHER_OBJECT_'):

            # Get other objects based on selected objects with different material
            for o in context.selected_objects:
                if o in objs or not o.data or not hasattr(o.data, 'materials'): continue
                if mat.name not in o.data.materials:
                    other_objs.append(o)

            # Try to get other_objects from bake info
            if overwrite_img:

                bi = segment.bake_info if segment else overwrite_img.y_bake_info

                scene_objs = get_scene_objects()
                for oo in bi.other_objects:
                    if oo.object:
                        if is_greater_than_280():
                            # Check if object is on current view layer
                            layer_cols = get_object_parent_layer_collections([], bpy.context.view_layer.layer_collection, oo.object)
                            if oo.object not in other_objs and any(layer_cols):
                                other_objs.append(oo.object)
                        else:
                            o = scene_objs.get(oo.object.name)
                            if o and o not in other_objs:
                                other_objs.append(o)

            if self.type == 'OTHER_OBJECT_CHANNELS':
                ch_other_objects, ch_other_mats, ch_other_sockets, ch_other_defaults, ori_mat_no_nodes = prepare_other_objs_channels(yp, other_objs)

            if not other_objs:
                if overwrite_img:
                    self.report({'ERROR'}, "No source objects found! They're probably deleted!")
                else: self.report({'ERROR'}, "Source objects must be selected and it should have different material!")
                return {'CANCELLED'}

        # Get tile numbers
        tilenums = [1001]
        if self.use_udim:
            tilenums = UDIM.get_tile_numbers(objs, self.uv_map)

        # Remember things
        book = remember_before_bake(yp, mat=mat)

        # FXAA doesn't work with hdr image
        # FXAA also does not works well with baked image with alpha, so other object bake will use SSAA instead
        use_fxaa = not self.hdr and self.fxaa and not self.type.startswith('OTHER_OBJECT_')

        # For now SSAA only works with other object baking
        use_ssaa = self.ssaa and self.type.startswith('OTHER_OBJECT_')

        # SSAA will multiply size by 2 then resize it back
        if use_ssaa:
            width = self.width * 2
            height = self.height * 2
        else:
            width = self.width
            height = self.height

        # If use baked disp, need to bake normal and height map first
        height_root_ch = get_root_height_channel(yp)
        if height_root_ch and self.use_baked_disp and not self.type.startswith('MULTIRES_'):

            # Check if baked displacement already there
            baked_disp = tree.nodes.get(height_root_ch.baked_disp)

            if baked_disp and baked_disp.image:
                disp_width = baked_disp.image.size[0]
                disp_height = baked_disp.image.size[1]
            else:
                disp_width = ypup.default_new_image_size
                disp_height = ypup.default_new_image_size

            if yp.baked_uv_name != '':
                disp_uv = yp.baked_uv_name
            else: disp_uv = yp.uvs[0].name
            
            # Use 1 sample for baking height
            prepare_bake_settings(book, objs, yp, samples=1, margin=self.margin, 
                    uv_map=self.uv_map, bake_type='EMIT', bake_device=self.bake_device
                    )

            # Bake height channel
            bake_channel(disp_uv, mat, node, height_root_ch, disp_width, disp_height)

            # Recover bake settings
            recover_bake_settings(book, yp)

            # Set baked name
            if yp.baked_uv_name == '':
                yp.baked_uv_name = disp_uv

            # Set to use baked
            yp.use_baked = True
            ori_subdiv_setup = height_root_ch.enable_subdiv_setup
            ori_subdiv_adaptive = height_root_ch.subdiv_adaptive
            height_root_ch.subdiv_adaptive = False

            if not height_root_ch.enable_subdiv_setup:
                height_root_ch.enable_subdiv_setup = True

        # To hold temporary objects
        temp_objs = []

        # Sometimes Cavity bake will create temporary objects
        if (self.type == 'CAVITY' and (self.subsurf_influence or self.use_baked_disp)):
            objs = temp_objs = get_duplicated_mesh_objects(scene, objs, True)

        # Join objects then extend with other objects
        elif self.type.startswith('OTHER_OBJECT_'):
            if len(objs) > 1:
                objs = [get_merged_mesh_objects(scene, objs)]
                temp_objs = objs.copy()

            objs.extend(other_objs)

        # Join objects if the number of objects is higher than one
        elif len(objs) > 1 and not is_join_objects_problematic(yp):
            objs = temp_objs = [get_merged_mesh_objects(scene, objs, True)]

        fill_mode = 'FACE'
        obj_vertex_indices = {}
        if self.type == 'SELECTED_VERTICES':
            if context.tool_settings.mesh_select_mode[0] or context.tool_settings.mesh_select_mode[1]:
                fill_mode = 'VERTEX'

            if is_greater_than_280():
                edit_objs = [o for o in objs if o.mode == 'EDIT']
            else: edit_objs = [context.object]

            for obj in edit_objs:
                mesh = obj.data
                bm = bmesh.from_edit_mesh(mesh)

                bm.verts.ensure_lookup_table()
                #bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                v_indices = []
                if fill_mode == 'FACE':
                    for face in bm.faces:
                        if face.select:
                            v_indices.append(face.index)
                            #for loop in face.loops:
                            #    v_indices.append(loop.index)

                else:
                    for vert in bm.verts:
                        if vert.select:
                            v_indices.append(vert.index)

                obj_vertex_indices[obj.name] = v_indices

            bpy.ops.object.mode_set(mode = 'OBJECT')
            for obj in objs:
                try:
                    vcol = new_vertex_color(obj, TEMP_VCOL)
                    set_obj_vertex_colors(obj, vcol.name, (0.0, 0.0, 0.0, 1.0))
                    set_active_vertex_color(obj, vcol)
                except: pass
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.mesh.y_vcol_fill(color_option ='WHITE')
            #return {'FINISHED'}
            bpy.ops.object.mode_set(mode = 'OBJECT')

        #return {'FINISHED'}

        # Prepare bake settings

        if self.type == 'AO':
            bake_type = 'AO'
        elif self.type == 'MULTIRES_NORMAL':
            bake_type = 'NORMALS'
        elif self.type == 'MULTIRES_DISPLACEMENT':
            bake_type = 'DISPLACEMENT'
        elif self.type == 'OTHER_OBJECT_NORMAL':
            bake_type = 'NORMAL'
        else: 
            bake_type = 'EMIT'

        # If use only local, hide other objects
        hide_other_objs = self.type != 'AO' or self.only_local

        # Fit tilesize to bake resolution if samples is equal 1
        if self.samples <= 1:
            tile_x = width
            tile_y = height
        else:
            tile_x = 256
            tile_y = 256

        prepare_bake_settings(book, objs, yp, samples=self.samples, margin=self.margin, 
                uv_map=self.uv_map, bake_type=bake_type, #disable_problematic_modifiers=True, 
                bake_device=self.bake_device, hide_other_objs=hide_other_objs, 
                bake_from_multires=self.type.startswith('MULTIRES_'), tile_x = tile_x, tile_y = tile_y, 
                use_selected_to_active=self.type.startswith('OTHER_OBJECT_'),
                max_ray_distance=self.max_ray_distance, cage_extrusion=self.cage_extrusion,
                source_objs=other_objs,
                )

        # Set multires level
        #ori_multires_levels = {}
        if self.type.startswith('MULTIRES_'): #or self.type == 'AO':
            for ob in objs:
                mod = get_multires_modifier(ob)

                #mod.render_levels = mod.total_levels
                if self.type.startswith('MULTIRES_'):
                    mod.render_levels = self.multires_base
                    mod.levels = self.multires_base

                #ori_multires_levels[ob.name] = mod.render_levels

        # Setup for cavity
        if self.type == 'CAVITY':

            tt = time.time()
            print('BAKE TO LAYER: Applying subsurf/multires for Cavity bake...')

            # Set vertex color for cavity
            for obj in objs:

                set_active_object(obj)

                if self.subsurf_influence or self.use_baked_disp:
                    need_to_be_applied_modifiers = []
                    for m in obj.modifiers:
                        if m.type in {'SUBSURF', 'MULTIRES'} and m.levels > 0 and m.show_viewport:

                            # Set multires to the highest level
                            if m.type == 'MULTIRES':
                                m.levels = m.total_levels

                            need_to_be_applied_modifiers.append(m)

                        # Also apply displace
                        if m.type == 'DISPLACE' and m.show_viewport:
                            need_to_be_applied_modifiers.append(m)

                    # Apply shape keys and modifiers
                    if any(need_to_be_applied_modifiers):
                        if obj.data.shape_keys:
                            bpy.ops.object.shape_key_remove(all=True, apply_mix=True)

                        for m in need_to_be_applied_modifiers:
                            bpy.ops.object.modifier_apply(modifier=m.name)

                # Create new vertex color for dirt
                try:
                    vcol = new_vertex_color(obj, TEMP_VCOL)
                    set_obj_vertex_colors(obj, vcol.name, (1.0, 1.0, 1.0, 1.0))
                    set_active_vertex_color(obj, vcol)
                except: pass

                bpy.ops.paint.vertex_color_dirt(dirt_angle=math.pi/2)
                bpy.ops.paint.vertex_color_dirt()

            print('BAKE TO LAYER: Applying subsurf/multires is done at', '{:0.2f}'.format(time.time() - tt), 'seconds!')

        # Setup for flow
        if self.type == 'FLOW':
            bpy.ops.object.mode_set(mode = 'OBJECT')
            for obj in objs:
                uv_layers = get_uv_layers(obj)
                main_uv = uv_layers.get(self.uv_map)
                straight_uv = uv_layers.get(self.uv_map_1)

                if main_uv and straight_uv:
                    flow_vcol = get_flow_vcol(obj, main_uv, straight_uv)

        # Flip normals setup
        if self.flip_normals:
            #ori_mode[obj.name] = obj.mode
            if is_greater_than_280():
                # Deselect other objects first
                for o in other_objs:
                    o.select_set(False)
                bpy.ops.object.mode_set(mode = 'EDIT')
                bpy.ops.mesh.reveal()
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.flip_normals()
                bpy.ops.object.mode_set(mode = 'OBJECT')
                # Reselect other objects
                for o in other_objs:
                    o.select_set(True)
            else:
                for obj in objs:
                    if obj in other_objs: continue
                    context.scene.objects.active = obj
                    bpy.ops.object.mode_set(mode = 'EDIT')
                    bpy.ops.mesh.reveal()
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.flip_normals()
                    bpy.ops.object.mode_set(mode = 'OBJECT')

        # More setup
        ori_mods = {}
        ori_viewport_mods = {}
        ori_mat_ids = {}
        ori_loop_locs = {}
        ori_multires_levels = {}

        for obj in objs:

            # Disable few modifiers
            ori_mods[obj.name] = [m.show_render for m in obj.modifiers]
            ori_viewport_mods[obj.name] = [m.show_viewport for m in obj.modifiers]
            if self.type.startswith('MULTIRES_'):
                mul = get_multires_modifier(obj)
                multires_index = 99
                if mul:
                    for i, m in enumerate(obj.modifiers):
                        if m == mul: multires_index = i
                        if i > multires_index: 
                            m.show_render = False
                            m.show_viewport = False
            elif obj not in other_objs:
                for m in get_problematic_modifiers(obj):
                    m.show_render = False

            ori_mat_ids[obj.name] = []
            ori_loop_locs[obj.name] = []

            if self.subsurf_influence and not self.use_baked_disp and not self.type.startswith('MULTIRES_'):
                for m in obj.modifiers:
                    if m.type == 'MULTIRES':
                        ori_multires_levels[obj.name] = m.render_levels
                        m.render_levels = m.total_levels
                        break

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
            src = None

            if hasattr(context.scene.cycles, 'use_fast_gi'):
                context.scene.cycles.use_fast_gi = True

            if context.scene.world:
                context.scene.world.light_settings.distance = self.ao_distance

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

        elif self.type == 'SELECTED_VERTICES':
            if is_greater_than_280():
                src = mat.node_tree.nodes.new('ShaderNodeVertexColor')
                src.layer_name = TEMP_VCOL
            else:
                src = mat.node_tree.nodes.new('ShaderNodeAttribute')
                src.attribute_name = TEMP_VCOL
            mat.node_tree.links.new(src.outputs[0], bsdf.inputs[0])
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

        elif self.type == 'FLOW':
            # Set vcol
            src = mat.node_tree.nodes.new('ShaderNodeAttribute')
            src.attribute_name = FLOW_VCOL

            mat.node_tree.links.new(src.outputs[0], bsdf.inputs[0])
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

        else:
            src = None
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

        # Get number of target images
        ch_ids = [0]
        
        # Other object channels related
        all_other_mats = []
        ori_sockets = {}

        if self.type == 'OTHER_OBJECT_CHANNELS':
            ch_ids = [i for i, coo in enumerate(ch_other_objects) if len(coo) > 0]

            # Get all other materials
            for oo in other_objs:
                for m in oo.data.materials:
                    if m == None or not m.use_nodes: continue
                    if m not in all_other_mats:
                        all_other_mats.append(m)

            # Remember original socket connected to outputs
            for m in all_other_mats:
                soc = None
                outputs = [n for n in m.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
                if outputs: 
                    for l in outputs[0].inputs[0].links:
                        soc = l.from_socket

                    # Create temporary emission
                    temp_emi = m.node_tree.nodes.get(TEMP_EMISSION)
                    if not temp_emi:
                        temp_emi = m.node_tree.nodes.new('ShaderNodeEmission')
                        temp_emi.name = TEMP_EMISSION
                        m.node_tree.links.new(temp_emi.outputs[0], outputs[0].inputs[0])

                ori_sockets[m.name] = soc

        for idx in ch_ids:

            # Image name and colorspace
            image_name = self.name
            colorspace = 'sRGB'

            if self.type == 'OTHER_OBJECT_CHANNELS':

                root_ch = yp.channels[idx]
                image_name += ' ' + yp.channels[idx].name

                # Hide irrelevant objects
                for oo in other_objs:
                    if oo not in ch_other_objects[idx]:
                        oo.hide_render = True
                    else: oo.hide_render = False

                if root_ch.type == 'NORMAL':
                    bake_type = 'NORMAL'

                    # Set back original socket
                    for m in all_other_mats:
                        outputs = [n for n in m.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
                        if outputs: 
                            m.node_tree.links.new(ori_sockets[m.name], outputs[0].inputs[0])

                else:
                    bake_type = 'EMIT'

                    # Set emission connection
                    for j, m in enumerate(ch_other_mats[idx]):
                        default = ch_other_defaults[idx][j]
                        socket = ch_other_sockets[idx][j]

                        temp_emi = m.node_tree.nodes.get(TEMP_EMISSION)
                        if not temp_emi: continue

                        if default != None:
                            # Set default
                            if type(default) == float:
                                temp_emi.inputs[0].default_value = (default, default, default, 1.0)
                            else: temp_emi.inputs[0].default_value = (default[0], default[1], default[2], 1.0)

                            # Break link
                            for l in temp_emi.inputs[0].links:
                                m.node_tree.links.remove(l)
                        elif socket:
                            m.node_tree.links.new(socket, temp_emi.inputs[0])

                colorspace = 'Non-Color' if root_ch.colorspace == 'LINEAR' else 'sRGB'

            elif self.type in {'BEVEL_NORMAL', 'MULTIRES_NORMAL', 'OTHER_OBJECT_NORMAL'}:
                colorspace = 'Non-Color'

            # Base color of baked image
            if self.type == 'AO':
                color = [1.0, 1.0, 1.0, 1.0] 
            elif self.type in {'BEVEL_NORMAL', 'MULTIRES_NORMAL', 'OTHER_OBJECT_NORMAL'}:
                if self.hdr:
                    color = [0.7354, 0.7354, 1.0, 1.0]
                else:
                    color = [0.5, 0.5, 1.0, 1.0] 
            elif self.type == 'FLOW':
                color = [0.5, 0.5, 0.0, 1.0]
            else:
                if self.hdr:
                    color = [0.7354, 0.7354, 0.7354, 1.0]
                else: color = [0.5, 0.5, 0.5, 1.0]

            # Make image transparent if its baked from other objects
            if self.type.startswith('OTHER_OBJECT_'):
                color[3] = 0.0

            # New target image
            if self.use_udim:
                image = bpy.data.images.new(name=image_name, width=width, height=height, 
                        alpha=True, float_buffer=self.hdr, tiled=True)

                # Fill tiles
                for tilenum in tilenums:
                    UDIM.fill_tile(image, tilenum, color, width, height)
                UDIM.initial_pack_udim(image, color)

                # Remember base color
                image.yui.base_color = color
            else:
                image = bpy.data.images.new(name=image_name,
                        width=width, height=height, alpha=True, float_buffer=self.hdr)

            image.generated_color = color
            image.colorspace_settings.name = colorspace

            # Set image filepath if overwrite image is found
            if overwrite_img:
                #if idx == 0:
                if idx == min(ch_ids):
                    if not overwrite_img.packed_file and overwrite_img.filepath != '':
                        image.filepath = overwrite_img.filepath
                else:
                    layer = yp.layers[yp.active_layer_index]
                    root_ch = yp.channels[idx]
                    ch = layer.channels[idx]

                    if root_ch.type == 'NORMAL':
                        source = get_channel_source_1(ch, layer)
                    else: source = get_channel_source(ch, layer)

                    if source and hasattr(source, 'image') and source.image and not source.image.packed_file and source.image.filepath != '':
                        image.filepath = source.image.filepath

            # Set bake image
            tex.image = image
            mat.node_tree.nodes.active = tex

            # Bake!
            if self.type.startswith('MULTIRES_'):
                bpy.ops.object.bake_image()
            else:
                if bake_type != 'EMIT':
                    bpy.ops.object.bake(type=bake_type)
                else: bpy.ops.object.bake()

            if use_fxaa: fxaa_image(image, False, bake_device=self.bake_device)

            # Bake alpha if baking other objects normal
            #if self.type.startswith('OTHER_OBJECT_'):
            if self.type == 'OTHER_OBJECT_NORMAL':
                temp_img = image.copy()
                temp_img.colorspace_settings.name = 'Non-Color'
                tex.image = temp_img

                # Set temp filepath
                if image.source == 'TILED':
                    temp_img.name = '__TEMP__'
                    UDIM.initial_pack_udim(temp_img)

                # Need to use clear so there's alpha on the baked image
                scene.render.bake.use_clear = True

                # Bake emit can will create alpha image
                bpy.ops.object.bake(type='EMIT')

                # Set tile pixels
                for tilenum in tilenums:

                    # Swap tile
                    if tilenum != 1001:
                        UDIM.swap_tile(image, 1001, tilenum)
                        UDIM.swap_tile(temp_img, 1001, tilenum)

                    # Copy alpha to RGB channel, so it can be fxaa-ed
                    copy_image_channel_pixels(temp_img, temp_img, 3, 0)
                    fxaa_image(temp_img, False, self.bake_device, first_tile_only=True)

                    # Copy alpha to actual image
                    copy_image_channel_pixels(temp_img, image, 0, 3)

                    # Swap tile again to recover
                    if tilenum != 1001:
                        UDIM.swap_tile(image, 1001, tilenum)
                        UDIM.swap_tile(temp_img, 1001, tilenum)

                # Remove temp image
                bpy.data.images.remove(temp_img)

            # Back to original size if using SSA
            if use_ssaa:
                image, temp_segment = resize_image(image, self.width, self.height, image.colorspace_settings.name, alpha_aware=True, bake_device=self.bake_device)

            new_segment_created = False

            if self.use_image_atlas:

                need_to_create_new_segment = False
                if segment:
                    ia_image = segment.id_data
                    if self.use_udim:
                        need_to_create_new_segment = ia_image.is_float != self.hdr
                        if need_to_create_new_segment:
                            UDIM.remove_udim_atlas_segment_by_name(ia_image, segment.name, yp)
                    else:
                        need_to_create_new_segment = self.width != segment.width or self.height != segment.height or ia_image.is_float != self.hdr
                        if need_to_create_new_segment:
                            segment.unused = True

                if not segment or need_to_create_new_segment:

                    if self.use_udim:
                        segment = UDIM.get_set_udim_atlas_segment(tilenums, color=(0,0,0,0), 
                                colorspace='sRGB', hdr=self.hdr, yp=yp)
                    else:
                        # Clearing unused image atlas segments
                        img_atlas = ImageAtlas.check_need_of_erasing_segments(yp, 'TRANSPARENT', self.width, self.height, self.hdr)
                        if img_atlas: ImageAtlas.clear_unused_segments(img_atlas.yia)

                        segment = ImageAtlas.get_set_image_atlas_segment(
                                self.width, self.height, 'TRANSPARENT', self.hdr, yp=yp) #, ypup.image_atlas_size)

                    new_segment_created = True

                ia_image = segment.id_data

                # Set baked image to segment
                if self.use_udim:
                    offset = get_udim_segment_mapping_offset(segment) * 10
                    copy_dict = {}
                    for tilenum in tilenums:
                        copy_dict[tilenum] = tilenum + offset
                    UDIM.copy_tiles(image, ia_image, copy_dict)
                else: copy_image_pixels(image, ia_image, segment)
                temp_img = image
                image = ia_image

                # Remove original baked image
                bpy.data.images.remove(temp_img)

            # Index 0 is the main image
            if idx == min(ch_ids):
                if overwrite_img:

                    active_id = yp.active_layer_index

                    if overwrite_img != image:
                        if segment and not self.use_image_atlas:
                            entities = ImageAtlas.replace_segment_with_image(yp, segment, image)
                            segment = None
                        else: entities = replace_image(overwrite_img, image, yp, self.uv_map)
                    elif segment: entities = ImageAtlas.get_entities_with_specific_segment(yp, segment)
                    else: entities = get_entities_with_specific_image(yp, image)

                    for entity in entities:
                        if new_segment_created:
                            entity.segment_name = segment.name
                            ImageAtlas.set_segment_mapping(entity, segment, image)

                        if entity.uv_name != self.uv_map:
                            entity.uv_name = self.uv_map

                    if self.target_type == 'LAYER':
                        layer_ids = [i for i, l in enumerate(yp.layers) if l in entities]
                        if entities and yp.active_layer_index not in layer_ids:
                            active_id = layer_ids[0]

                        # Refresh uv
                        refresh_temp_uv(context.object, yp.layers[active_id])

                        # Refresh Neighbor UV resolution
                        set_uv_neighbor_resolution(yp.layers[active_id])

                    elif self.target_type == 'MASK':
                        masks = []
                        for l in yp.layers:
                            masks.extend([m for m in l.masks if m in entities])
                        if masks: 
                            masks[0].active_edit = True

                            # Refresh uv
                            refresh_temp_uv(context.object, masks[0])

                            # Refresh Neighbor UV resolution
                            set_uv_neighbor_resolution(masks[0])

                elif self.target_type == 'LAYER':

                    layer_name = image.name if not self.use_image_atlas else self.name

                    if self.use_image_atlas:
                        layer_name = get_unique_name(layer_name, yp.layers)

                    yp.halt_update = True
                    layer = Layer.add_new_layer(node.node_tree, layer_name, 'IMAGE', int(self.channel_idx), self.blend_type, 
                            self.normal_blend_type, self.normal_map_type, 'UV', self.uv_map, image, None, segment
                            )
                    yp.halt_update = False
                    active_id = yp.active_layer_index

                    if segment:
                        ImageAtlas.set_segment_mapping(layer, segment, image)

                    # Refresh uv
                    refresh_temp_uv(context.object, layer)

                    # Refresh Neighbor UV resolution
                    set_uv_neighbor_resolution(layer)


                else:
                    mask_name = image.name if not self.use_image_atlas else self.name

                    if self.use_image_atlas:
                        mask_name = get_unique_name(mask_name, active_layer.masks)

                    mask = Mask.add_new_mask(active_layer, mask_name, 'IMAGE', 'UV', self.uv_map, image, None, segment)
                    mask.active_edit = True

                    rearrange_layer_nodes(active_layer)
                    reconnect_layer_nodes(active_layer)

                    active_id = yp.active_layer_index

                    if segment:
                        ImageAtlas.set_segment_mapping(mask, segment, image)

                    # Refresh uv
                    refresh_temp_uv(context.object, mask)

                    # Refresh Neighbor UV resolution
                    set_uv_neighbor_resolution(mask)

            # Indices > 0 are for channel override images
            else:
                # Set images to channel override
                layer = yp.layers[yp.active_layer_index]
                root_ch = yp.channels[idx]
                ch = layer.channels[idx]
                ch.enable = True

                # Normal channel will use second override
                if root_ch.type == 'NORMAL':
                    ch.normal_map_type = 'NORMAL_MAP'
                    ch.override_1 = True
                    ch.override_1_type = 'IMAGE'
                    source = get_channel_source_1(ch, layer)
                else:
                    ch.override = True
                    ch.override_type = 'IMAGE'
                    source = get_channel_source(ch, layer)

                # If image already exists on source
                old_image = None
                if source.image and image != source.image:
                    old_image = source.image
                    source_name = old_image.name
                    current_name = image.name

                    old_image.name = '_____temp'
                    image.name = source_name
                    old_image.name = current_name
                    
                # Set image to source
                source.image = image

                # Remove image if it's not used anymore
                if old_image: safe_remove_image(old_image)

            # Set bake info to image/segment
            bi = segment.bake_info if segment else image.y_bake_info

            bi.is_baked = True
            bi.bake_type = self.type
            for attr in dir(bi):
                #if attr in dir(self):
                if attr.startswith('__'): continue
                if attr.startswith('bl_'): continue
                if attr in {'rna_type'}: continue
                try: setattr(bi, attr, getattr(self, attr))
                except: pass

            if other_objs:

                # Remember other objects to bake info
                for o in other_objs:
                    if not any([oo for oo in bi.other_objects if oo.object == o]):
                        oo = bi.other_objects.add()
                        oo.object = o

                # Remove unused other objects on bake info
                for i, oo in reversed(list(enumerate(bi.other_objects))):
                    if oo.object not in other_objs:
                        bi.other_objects.remove(i)

            if self.type == 'SELECTED_VERTICES':
                #fill_mode = 'FACE'
                #obj_vertex_indices = {}
                bi.selected_face_mode = True if fill_mode == 'FACE' else False

                # Clear selected objects first
                bi.selected_objects.clear()

                # Collect object to bake info
                for obj_name, v_indices in obj_vertex_indices.items():
                    obj = bpy.data.objects.get(obj_name)
                    bso = bi.selected_objects.add()
                    bso.object = obj

                    # Collect selected vertex data to bake info
                    for vi in v_indices:
                        bvi = bso.selected_vertex_indices.add()
                        bvi.index = vi

        # Recover other yps
        if self.type == 'OTHER_OBJECT_CHANNELS':
            for m in all_other_mats:
                # Set back original socket
                outputs = [n for n in m.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
                if outputs: 
                    m.node_tree.links.new(ori_sockets[m.name], outputs[0].inputs[0])

                # Remove temp emission
                temp_emi = m.node_tree.nodes.get(TEMP_EMISSION)
                if temp_emi: m.node_tree.nodes.remove(temp_emi)

            # Recover other objects material settings
            recover_other_objs_channels(other_objs, ori_mat_no_nodes)

        # Remove temp bake nodes
        simple_remove_node(mat.node_tree, tex)
        #simple_remove_node(mat.node_tree, srgb2lin)
        simple_remove_node(mat.node_tree, bsdf)
        if src: simple_remove_node(mat.node_tree, src)
        if normal_bake: simple_remove_node(mat.node_tree, normal_bake)
        if geometry: simple_remove_node(mat.node_tree, geometry)
        if vector_math: simple_remove_node(mat.node_tree, vector_math)
        if vector_math_1: simple_remove_node(mat.node_tree, vector_math_1)

        # Recover original bsdf
        mat.node_tree.links.new(ori_bsdf, output.inputs[0])

        #return {'FINISHED'}

        for obj in objs:
            # Recover modifiers
            for i, m in enumerate(obj.modifiers):
                #print(obj.name, i)
                if i >= len(ori_mods[obj.name]): break
                if ori_mods[obj.name][i] != m.show_render:
                    m.show_render = ori_mods[obj.name][i]
                if i >= len(ori_viewport_mods[obj.name]): break
                if ori_viewport_mods[obj.name][i] != m.show_render:
                    m.show_viewport = ori_viewport_mods[obj.name][i]

            # Recover multires levels
            for m in obj.modifiers:
                if m.type == 'MULTIRES' and obj.name in ori_multires_levels:
                    m.render_levels = ori_multires_levels[obj.name]
                    break

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

            # Delete temp vcol
            vcols = get_vertex_colors(obj)
            vcol = vcols.get(TEMP_VCOL)
            if vcol: vcols.remove(vcol)

        # Recover flip normals setup
        if self.flip_normals:
            #bpy.ops.object.mode_set(mode = 'EDIT')
            #bpy.ops.mesh.flip_normals()
            #bpy.ops.mesh.select_all(action='DESELECT')
            #bpy.ops.object.mode_set(mode = ori_mode)
            if is_greater_than_280():
                # Deselect other objects first
                for o in other_objs:
                    o.select_set(False)
                bpy.ops.object.mode_set(mode = 'EDIT')
                bpy.ops.mesh.reveal()
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.flip_normals()
                bpy.ops.object.mode_set(mode = 'OBJECT')
                # Reselect other objects
                for o in other_objs:
                    o.select_set(True)
            else:
                for obj in objs:
                    if obj in other_objs: continue
                    context.scene.objects.active = obj
                    bpy.ops.object.mode_set(mode = 'EDIT')
                    bpy.ops.mesh.reveal()
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.flip_normals()
                    bpy.ops.object.mode_set(mode = 'OBJECT')

        # Recover subdiv setup
        #if height_root_ch and self.use_baked_disp:
        if height_root_ch and self.use_baked_disp and not self.type.startswith('MULTIRES_'):
            yp.use_baked = False
            height_root_ch.subdiv_adaptive = ori_subdiv_adaptive
            if height_root_ch.enable_subdiv_setup != ori_subdiv_setup:
                height_root_ch.enable_subdiv_setup = ori_subdiv_setup

        # Remove flow vcols
        if self.type == 'FLOW':
            for obj in objs:
                vcols = get_vertex_colors(obj)
                flow_vcol = vcols.get(FLOW_VCOL)
                if flow_vcol:
                    vcols.remove(flow_vcol)

        # Recover bake settings
        recover_bake_settings(book, yp, mat=mat)

        # Remove temporary objects
        if temp_objs:
            for o in temp_objs:
                m = o.data
                bpy.data.objects.remove(o)
                bpy.data.meshes.remove(m)

        #return {'FINISHED'}

        # Check linear nodes becuse sometimes bake results can be linear or srgb
        check_yp_linear_nodes(yp, reconnect=True)

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

        print('BAKE TO LAYER: Baking', image.name, 'is done at', '{:0.2f}'.format(time.time() - T), 'seconds!')

        return {'FINISHED'}

class YDuplicateLayerToImage(bpy.types.Operator):
    bl_idname = "node.y_duplicate_layer_to_image"
    bl_label = "Duplicate Layer/Mask To Image"
    bl_description = "Duplicate Layer/Mask to an image"
    bl_options = {'REGISTER', 'UNDO'}

    name : StringProperty(default='')

    uv_map : StringProperty(default='', update=update_bake_to_layer_uv_map)
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    hdr : BoolProperty(name='32 bit Float', default=False)

    width : IntProperty(name='Width', default = 1234, min=1, max=4096)
    height : IntProperty(name='Height', default = 1234, min=1, max=4096)

    margin : IntProperty(name='Bake Margin',
            description = 'Bake margin in pixels',
            default=5, min=0, subtype='PIXEL')

    bake_device : EnumProperty(
            name='Bake Device',
            description='Device to use for baking',
            items = (('GPU', 'GPU Compute', ''),
                     ('CPU', 'CPU', '')),
            default='CPU'
            )

    fxaa : BoolProperty(name='Use FXAA', 
            description = "Use FXAA to baked image (doesn't work with float images)",
            default=True)

    use_image_atlas : BoolProperty(
            name = 'Use Image Atlas',
            description='Use Image Atlas',
            default=False)

    blur : BoolProperty(name='Use Blur', 
            description = "Use blur to baked image",
            default=False)

    blur_factor : FloatProperty(name='Blur Factor',
            description = "Blur factor to baked image",
            default=1.0, min=0.0, max=100.0
            )

    disable_current : BoolProperty(
            name = 'Disable current layer/mask',
            description='Disable current layer/mask',
            default=True)

    use_udim : BoolProperty(
            name = 'Use UDIM Tiles',
            description='Use UDIM Tiles',
            default=False)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def invoke(self, context, event):

        obj = context.object
        ypup = get_user_preferences()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        self.entity = context.entity
        self.layer = None
        self.mask = None

        if not hasattr(context, 'entity'):
            return self.execute(context)

        # Check entity
        m1 = re.match(r'^yp\.layers\[(\d+)\]$', self.entity.path_from_id())
        m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', self.entity.path_from_id())

        if m1: 
            self.layer = yp.layers[int(m1.group(1))]
            self.mask = None
            self.index = int(m1.group(1))
        elif m2: 
            self.layer = yp.layers[int(m2.group(1))]
            self.mask = self.layer.masks[int(m2.group(2))]
            self.index = int(m2.group(2))
        else: 
            return self.execute(context)

        if self.mask:
            self.name = self.mask.name
            if not self.name.endswith(' Image'):
                self.name += ' Image'
            self.name = get_unique_name(self.name, self.layer.masks)
        else:
            self.name = self.layer.name
            if not self.name.endswith(' Image'):
                self.name += ' Image'
            self.name = get_unique_name(self.name, yp.layers)

        # Use user preference default image size if input uses default image size
        if self.width == 1234 and self.height == 1234:
            self.width = self.height = ypup.default_new_image_size

        # Use active uv layer name by default
        uv_layers = get_uv_layers(obj)

        # UV Map collections update
        self.uv_map_coll.clear()
        for uv in uv_layers:
            if not uv.name.startswith(TEMP_UV):
                self.uv_map_coll.add().name = uv.name

        if len(self.uv_map_coll) > 0:
            self.uv_map = self.uv_map_coll[0].name

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        ypup = get_user_preferences()

        # New image cannot use more pixels than the image atlas
        if self.use_image_atlas:
            if self.hdr: max_size = ypup.hdr_image_atlas_size
            else: max_size = ypup.image_atlas_size
            if self.width > max_size: self.width = max_size
            if self.height > max_size: self.height = max_size

        return True

    def draw(self, context):

        if is_greater_than_280():
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)

        col = row.column(align=False)

        col.label(text='Name:')
        col.label(text='')
        col.label(text='Width:')
        col.label(text='Height:')
        col.label(text='UV Map:')
        col.label(text='Margin:')
        if is_greater_than_280():
            col.separator()
            col.label(text='Bake Device:')
        col.separator()
        col.label(text='')
        col.label(text='')
        col.label(text='')
        #col.label(text='Blur:')

        col = row.column(align=False)

        col.prop(self, 'name', text='')
        col.prop(self, 'hdr')
        col.prop(self, 'width', text='')
        col.prop(self, 'height', text='')
        col.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')
        col.prop(self, 'margin', text='')

        if is_greater_than_280():
            col.separator()
            col.prop(self, 'bake_device', text='')
        col.separator()
        col.prop(self, 'fxaa')
        ccol = col.column(align=True)
        ccol.prop(self, 'use_image_atlas')
        if self.mask:
            col.prop(self, 'disable_current', text='Disable Current Mask')
        else: col.prop(self, 'disable_current', text='Disable Current Layer')

        rrow = col.row(align=True)
        rrow.prop(self, 'blur')
        if self.blur:
            rrow.prop(self, 'blur_factor', text='')

    def execute(self, context):

        if not self.layer:
            self.report({'ERROR'}, "Invalid context!")
            return {'CANCELLED'}

        if self.layer and not self.mask:
            self.report({'ERROR'}, "This feature is not implemented yet!")
            return {'CANCELLED'}

        T = time.time()
        mat = get_active_material()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        tree = node.node_tree

        objs = [context.object]
        meshes = [context.object.data]

        if mat.users > 1:
            for ob in get_scene_objects():
                if ob.type != 'MESH': continue
                if hasattr(ob, 'hide_viewport') and ob.hide_viewport: continue
                if len(get_uv_layers(ob)) == 0: continue
                if len(ob.data.polygons) == 0: continue

                # Do not bake objects with hide_render on
                if ob.hide_render: continue
                if not in_renderable_layer_collection(ob): continue

                for i, m in enumerate(ob.data.materials):
                    if m == mat:
                        ob.active_material_index = i
                        if ob not in objs and ob.data not in meshes:
                            objs.append(ob)
                            meshes.append(ob.data)

        if not objs:
            self.report({'ERROR'}, "No valid objects found to bake!")
            return {'CANCELLED'}

        # Remember things
        book = remember_before_bake(yp)

        # FXAA doesn't work with hdr image
        # FXAA also does not works well with baked image with alpha, so other object bake will use SSAA instead
        use_fxaa = not self.hdr and self.fxaa

        samples = 1
        if self.mask and self.mask.enable_blur_vector:
            samples = 4096 if is_greater_than_300() else 128

        # Preview setup
        ori_channel_index = yp.active_channel_index
        ori_preview_mode = yp.preview_mode
        ori_layer_preview_mode = yp.layer_preview_mode
        ori_layer_preview_mode_type = yp.layer_preview_mode_type

        self.layer.enable = True

        if self.mask: 
            self.mask.enable = True
            self.mask.active_edit = True

        yp.layer_preview_mode_type = 'SPECIFIC_MASK' if self.mask else 'LAYER'
        yp.layer_preview_mode = True

        # Set active channel so preview will output right value
        for i, ch in enumerate(self.layer.channels):
            if self.mask:
                if ch.enable and self.mask.channels[i].enable:
                    yp.active_channel_index = i
                    break
            else:
                if ch.enable:
                    yp.active_channel_index = i
                    break

        # Modifier setups
        ori_mods = {}
        ori_viewport_mods = {}

        for obj in objs:

            # Disable few modifiers
            ori_mods[obj.name] = [m.show_render for m in obj.modifiers]
            ori_viewport_mods[obj.name] = [m.show_viewport for m in obj.modifiers]

            for m in get_problematic_modifiers(obj):
                m.show_render = False

        prepare_bake_settings(book, objs, yp, samples=samples, margin=self.margin, 
                uv_map=self.uv_map, bake_type='EMIT', bake_device=self.bake_device
                )

        # Create bake nodes
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')

        if self.mask:
            color = (0,0,0,1)
            color_str = 'BLACK'
            colorspace = 'Non-Color'
        else: 
            color = (0,0,0,0)
            color_str = 'TRANSPARENT'
            colorspace = 'sRGB'

        # Create image
        if self.use_udim:
            image = bpy.data.images.new(name=self.name,
                    width=self.width, height=self.height, alpha=True, float_buffer=self.hdr, tiled=True)

            tilenums = UDIM.get_tile_numbers(objs, self.uv_map)

            # Fill tiles
            for tilenum in tilenums:
                UDIM.fill_tile(image, tilenum, color, self.width, self.height)
            UDIM.initial_pack_udim(image, color)

            # Remember base color
            image.yia.color = color_str
        else:
            image = bpy.data.images.new(name=self.name,
                    width=self.width, height=self.height, alpha=True, float_buffer=self.hdr)

        image.generated_color = color
        image.colorspace_settings.name = colorspace

        # Set bake image
        tex.image = image
        mat.node_tree.nodes.active = tex

        # Bake!
        bpy.ops.object.bake()

        if use_fxaa: fxaa_image(image, False, bake_device=self.bake_device)
        if self.blur: 
            samples = 4096 if is_greater_than_300() else 128
            blur_image(image, False, bake_device=self.bake_device, factor=self.blur_factor, samples=samples)

        if self.mask:
            mask_name = image.name if not self.use_image_atlas else self.name

            segment = None
            if self.use_image_atlas:
                mask_name = get_unique_name(mask_name, self.layer.masks)

                if self.use_udim:
                    segment = UDIM.get_set_udim_atlas_segment(tilenums, color=(0,0,0,1), 
                            colorspace='Non-Color', hdr=self.hdr, yp=yp)
                else:
                    # Clearing unused image atlas segments
                    img_atlas = ImageAtlas.check_need_of_erasing_segments(yp, 'BLACK', self.width, self.height, self.hdr)
                    if img_atlas: ImageAtlas.clear_unused_segments(img_atlas.yia)

                    segment = ImageAtlas.get_set_image_atlas_segment(
                            self.width, self.height, 'BLACK', self.hdr, yp=yp) #, ypup.image_atlas_size)

                ia_image = segment.id_data

                # Set baked image to segment
                if self.use_udim:
                    offset = get_udim_segment_mapping_offset(segment) * 10
                    copy_dict = {}
                    for tilenum in tilenums:
                        copy_dict[tilenum] = tilenum + offset
                    UDIM.copy_tiles(image, ia_image, copy_dict)
                else: copy_image_pixels(image, ia_image, segment)
                temp_img = image
                image = ia_image

                # Remove original baked image
                bpy.data.images.remove(temp_img)

            # Disable source mask
            if self.mask and self.disable_current:
                self.mask.enable = False

            # Create new mask
            mask = Mask.add_new_mask(self.layer, mask_name, 'IMAGE', 'UV', self.uv_map, image, None, segment)

            # Set mask properties
            mask.intensity_value = self.mask.intensity_value
            mask.blend_type = self.mask.blend_type
            for i, c in enumerate(self.mask.channels):
                mask.channels[i].enable = c.enable

            # Set newly created mask active
            mask.active_edit = True

            # Reorder index
            self.layer.masks.move(len(self.layer.masks)-1, self.index+1)
            layer_tree = get_tree(self.layer)
            check_mask_mix_nodes(self.layer, layer_tree)
            check_mask_source_tree(self.layer) #, bump_ch)
            mask = self.layer.masks[self.index+1]

            if segment:
                ImageAtlas.set_segment_mapping(mask, segment, image)

            # Refresh uv
            refresh_temp_uv(context.object, mask)

            # Refresh Neighbor UV resolution
            set_uv_neighbor_resolution(mask)

            rearrange_layer_nodes(self.layer)
            reconnect_layer_nodes(self.layer)

        # Remove temp bake nodes
        simple_remove_node(mat.node_tree, tex)

        # Recover bake settings
        recover_bake_settings(book, yp)

        # Recover modifiers
        for obj in objs:
            # Recover modifiers
            for i, m in enumerate(obj.modifiers):
                #print(obj.name, i)
                if i >= len(ori_mods[obj.name]): break
                if ori_mods[obj.name][i] != m.show_render:
                    m.show_render = ori_mods[obj.name][i]
                if i >= len(ori_viewport_mods[obj.name]): break
                if ori_viewport_mods[obj.name][i] != m.show_render:
                    m.show_viewport = ori_viewport_mods[obj.name][i]

        # Recover preview
        yp.active_channel_index = ori_channel_index
        if yp.preview_mode != ori_preview_mode:
            yp.preview_mode = ori_preview_mode
        if yp.layer_preview_mode != ori_layer_preview_mode:
            yp.layer_preview_mode = ori_layer_preview_mode
        if yp.layer_preview_mode_type != ori_layer_preview_mode_type:
            yp.layer_preview_mode_type = ori_layer_preview_mode_type

        return {"FINISHED"}

def register():
    bpy.utils.register_class(YBakeToLayer)
    bpy.utils.register_class(YRemoveBakeInfoOtherObject)
    bpy.utils.register_class(YTryToSelectBakedVertexSelect)
    bpy.utils.register_class(YDuplicateLayerToImage)

def unregister():
    bpy.utils.unregister_class(YBakeToLayer)
    bpy.utils.unregister_class(YRemoveBakeInfoOtherObject)
    bpy.utils.unregister_class(YTryToSelectBakedVertexSelect)
    bpy.utils.unregister_class(YDuplicateLayerToImage)
