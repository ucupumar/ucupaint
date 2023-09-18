from bpy.types import Context
from .common import * 
from .lib import *
from zipfile import ZipFile
from bpy_extras.image_utils import load_image  

from . import lib, Layer, UDIM

import bpy, threading, os, requests, json
from bpy.props import *
from bpy.types import PropertyGroup, Panel, Operator, UIList, Scene

THREAD_SEARCHING = "thread_searching"
# thread_search:threading.Thread # progress:int
# global previews_collection
# preview_items = []
assets_lib = {}
last_search = {}

threads = {} # progress:int,
 
class MaterialItem(PropertyGroup): 
    name: StringProperty( name="Name", description="Material name", default="Untitled") 
    thumb: IntProperty( name="thumbnail", description="", default=0)

class DownloadThread(PropertyGroup):
    asset_id : StringProperty()
    asset_attribute: StringProperty()
    file_path : StringProperty()
    alive : BoolProperty(default = False)
    file_size:IntProperty()
    progress : IntProperty(
        default = 0,
        min = 0,
        max = 100,
        description = 'Progress of the download',
        subtype = 'PERCENTAGE'
    )


def update_input_search(self, context):
    if self.input_last == self.input_search:
        print("no search:"+self.input_search)
        return
    
    self.input_last = self.input_search

    txlib = context.scene.texlib
    txlib.material_items.clear()

    if self.input_search == '':
        last_search.clear()
        return

    thread_search = threading.Thread(target=searching_material, args=(self.input_search,context))
    thread_search.progress = 0
    thread_search.cancel = False
    threads[THREAD_SEARCHING] = thread_search

    thread_search.start()

    self.searching_download.progress = 0
    self.searching_download.alive = True

class TexLibProps(PropertyGroup):
    page: IntProperty(name="page", default= 0)
    input_search:StringProperty(name="Search", update=update_input_search)
    input_last:StringProperty()
    material_items:CollectionProperty(type= MaterialItem)
    material_index:IntProperty(default=0, name="Material index")

    downloads:CollectionProperty(type=DownloadThread)
    searching_download:PointerProperty(type=DownloadThread)
    selected_download_item:IntProperty(default=0)

class TexLibAddToUcupaint(Operator):
    """Open Multiple Textures to Layer Ucupaint"""

    bl_label = ""
    bl_idname = "texlib.add_to_ucupaint"
    attribute:StringProperty()
    id:StringProperty()

    texcoord_type : EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_map : StringProperty(default='')
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    add_mask : BoolProperty(
            name = 'Add Mask',
            description = 'Add mask to new layer',
            default = False)

    mask_type : EnumProperty(
            name = 'Mask Type',
            description = 'Mask type',
            items = (('IMAGE', 'Image', '', 'IMAGE_DATA', 0),
                ('VCOL', 'Vertex Color', '', 'GROUP_VCOL', 1)),
            default = 'IMAGE')

    mask_color : EnumProperty(
            name = 'Mask Color',
            description = 'Mask Color',
            items = (
                ('WHITE', 'White (Full Opacity)', ''),
                ('BLACK', 'Black (Full Transparency)', ''),
                ),
            default='BLACK')

    mask_width : IntProperty(name='Mask Width', default = 1234, min=1, max=4096)
    mask_height : IntProperty(name='Mask Height', default = 1234, min=1, max=4096)

    mask_uv_name : StringProperty(default='', update=Layer.update_new_layer_mask_uv_map)
    mask_use_hdr : BoolProperty(name='32 bit Float', default=False)

    use_udim_for_mask : BoolProperty(
            name = 'Use UDIM Tiles for Mask',
            description='Use UDIM Tiles for Mask',
            default=False)

    use_image_atlas_for_mask : BoolProperty(
            name = 'Use Image Atlas for Mask',
            description='Use Image Atlas for Mask',
            default=False)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def invoke(self, context, event):
        obj = context.object
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        ypup = get_user_preferences()

        # Use user preference default image size if input uses default image size
        if self.mask_width == 1234 and self.mask_height == 1234:
            self.mask_width = self.mask_height = ypup.default_new_image_size

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH':
            uv_name = get_default_uv_name(obj, yp)
            self.uv_map = uv_name
            if self.add_mask and self.mask_type == 'IMAGE': self.mask_uv_name = uv_name

            # UV Map collections update
            self.uv_map_coll.clear()
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        # Normal map is the default
        #self.normal_map_type = 'NORMAL_MAP'

        #return context.window_manager.invoke_props_dialog(self)
        # context.window_manager.fileselect_add(self)
        return context.window_manager.invoke_props_dialog(self, width=320)
    
    def check(self, context):
        ypup = get_user_preferences()

        # New image cannot use more pixels than the image atlas
        if self.is_mask_using_image_atlas():
            if self.mask_use_hdr: mask_max_size = ypup.hdr_image_atlas_size
            else: mask_max_size = ypup.image_atlas_size
            if self.mask_width > mask_max_size: self.mask_width = mask_max_size
            if self.mask_height > mask_max_size: self.mask_height = mask_max_size

        # Init mask uv name
        if self.add_mask and self.mask_uv_name == '':

            node = get_active_ypaint_node()
            yp = node.node_tree.yp
            obj = context.object

            uv_name = get_default_uv_name(obj, yp)
            self.mask_uv_name = uv_name

        return True
    
    def draw(self, context):
        obj = context.object

        row = self.layout.row()

        col = row.column()
        col.label(text='Vector:')

        col.label(text='')
        if self.add_mask:
            col.label(text='Mask Type:')
            col.label(text='Mask Color:')
            if self.mask_type == 'IMAGE':
                col.label(text='')
                col.label(text='Mask Width:')
                col.label(text='Mask Height:')
                col.label(text='Mask UV Map:')
                col.label(text='')

        col = row.column()
        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            #crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')
            crow.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

        col.prop(self, 'add_mask', text='Add Mask')
        if self.add_mask:
            col.prop(self, 'mask_type', text='')
            col.prop(self, 'mask_color', text='')
            if self.mask_type == 'IMAGE':
                col.prop(self, 'mask_use_hdr')
                col.prop(self, 'mask_width', text='')
                col.prop(self, 'mask_height', text='')
                #col.prop_search(self, "mask_uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')
                col.prop_search(self, "mask_uv_name", self, "uv_map_coll", text='', icon='GROUP_UVS')
                if UDIM.is_udim_supported():
                    col.prop(self, 'use_udim_for_mask')
                ccol = col.column()
                ccol.active = not self.use_udim_for_mask
                ccol.prop(self, 'use_image_atlas_for_mask', text='Use Image Atlas')

        # self.layout.prop(self, 'relative')

    def execute(self, context):
        T = time.time()

        lib = assets_lib[self.id]
        attr_dwn = lib["downloads"][self.attribute]
        directory = attr_dwn["location"]
        import_list = os.listdir(directory)

        if not Layer.open_images_to_single_layer(context, directory, import_list, self.texcoord_type, self.uv_map
                                                 ,self.add_mask, self.mask_type, self.mask_color, self.mask_use_hdr, 
                                                self.mask_uv_name, self.mask_width, self.mask_height, self.use_image_atlas_for_mask, 
                                                use_udim_for_mask=self.is_mask_using_udim()):
            return {'CANCELLED'}

        return {'FINISHED'}
    
    def is_mask_using_udim(self):
        return self.use_udim_for_mask and UDIM.is_udim_supported()
    
    def is_mask_using_image_atlas(self):
        return self.use_image_atlas_for_mask and not self.is_mask_using_udim()

class TexLibCancelDownload(Operator):
    """Cancel downloading textures"""

    bl_label = ""
    bl_idname = "texlib.cancel"
    attribute:StringProperty()
    id:StringProperty()

    def execute(self, context):
        print("cancel cancel")

        return {'FINISHED'}


class TexLibDownload(Operator):
    """Download textures from source"""

    bl_label = ""
    bl_idname = "texlib.download"
    

    attribute:StringProperty()
    id:StringProperty()
    file_size:IntProperty
    file_exist:BoolProperty(default=False)

    def execute(self, context):
       
        lib = assets_lib[self.id]
        attr_dwn = lib["downloads"][self.attribute]
        link = attr_dwn["link"]
        directory = attr_dwn["location"]
        file_name = os.path.join(directory, attr_dwn["fileName"])

        print("setar =",self.attribute, "selected = "+self.id, "lib =", link)

        if not os.path.exists(directory):
            # print("make dir "+directory)
            os.makedirs(directory)

        thread_id = _get_thread_id(self.id, self.attribute)
        new_thread = threading.Thread(target=download_stream, args=(link,file_name,thread_id,))
        new_thread.progress = 0
        new_thread.cancel = False
        threads[_get_thread_id(self.id, self.attribute)] = new_thread

        new_thread.start()

        texlib = context.scene.texlib
        new_dwn:DownloadThread = texlib.downloads.add()
        new_dwn.asset_id = self.id
        new_dwn.file_path = file_name
        new_dwn.asset_attribute = self.attribute
        new_dwn.alive = True
        new_dwn.file_size = attr_dwn["size"]
        new_dwn.progress = 0

        return {'FINISHED'}

class TexLibBrowser(Panel):
    bl_label = "Texlib Browser"
    bl_idname = "TEXLIB_PT_Browser"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Ucupaint"
    

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        texlib:TexLibProps = scene.texlib
        sel_index = texlib.material_index


        layout.prop(texlib, "input_search")
        searching_dwn = texlib.searching_download
       
        if searching_dwn.alive:
            prog = searching_dwn.progress

            if prog >= 0:
                row_search = layout.row()

                if prog < 10:
                    row_search.label(text="Searching...")
                else:
                    row_search.label(text="Retrieving thumbnails..."+str(prog)+"%")
                row_search.operator("texlib.cancel_search", icon="CANCEL")

        if len(texlib.material_items):
            my_list = texlib.material_items

            layout.separator()
            layout.label(text="Textures:")
            layout.template_list("TEXLIB_UL_Material", "material_list", texlib, "material_items", texlib, "material_index")
            if sel_index < len(my_list):
                sel_mat:MaterialItem = my_list[sel_index]
                mat_id:str = sel_mat.name
                layout.separator()
                layout.label(text="Preview:")
                prev_box = layout.box()
                selected_mat = prev_box.column(align=True)
                selected_mat.alignment = "CENTER"
                selected_mat.template_icon(icon_value=sel_mat.thumb, scale=5.0)
                selected_mat.label(text=mat_id)
                downloads = assets_lib[mat_id]["downloads"]

                layout.separator()
                layout.label(text="Attributes:")
                for d in downloads:
                    dwn = downloads[d]
                    ui_attr = layout.split(factor=0.7)
                    # row.alignment = "LEFT"

                    ukuran = round(dwn["size"] / 1000000,2)

                    check_exist:bool = False
                    lokasi = dwn["location"]
                    if os.path.exists(lokasi):
                        files = os.listdir(lokasi)
                        for f in files:
                            if mat_id in f:
                                check_exist = True
                                break
                    else:
                        check_exist = False
                    
                    row = ui_attr.row()

                    row.label(text=d, )
                    # rr.label(text=d, )
                    row.label(text=str(ukuran)+ "MB")

                    thread_id = _get_thread_id(mat_id, d)
                    dwn_thread = _get_thread(thread_id)

                    btn_row = ui_attr.row()
                    btn_row.alignment = "RIGHT"

                    if dwn_thread != None:
                        btn_row.label(text=str(dwn_thread.progress)+"%")
                        btn_row.operator("texlib.cancel", icon="X")
                    else:
                        if check_exist:
                            op:TexLibAddToUcupaint = btn_row.operator("texlib.add_to_ucupaint", icon="ADD")
                            op.attribute = d
                            op.id = sel_mat.name
                        
                        op:TexLibDownload = btn_row.operator("texlib.download", icon="IMPORT")
                        op.attribute = d
                        op.id = sel_mat.name
                        op.file_exist = check_exist

        if len(texlib.downloads):
            layout.separator()
            layout.label(text="Downloads:")
            layout.template_list("TEXLIB_UL_Downloads", "download_list", texlib, "downloads", texlib, "selected_download_item")




class TEXLIB_UL_Downloads(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        """Demo UIList."""
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "progress", slider=True, text=item.asset_id+" | "+item.asset_attribute)
            row.operator("texlib.cancel", icon="X")
       

class TEXLIB_UL_Material(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        """Demo UIList."""

        row = layout.row(align=True)
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row.template_icon(icon_value = item.thumb, scale = 1.0)
            row.label(text=item.name)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon_value = item.thumb)

class TexLibCancelSearch(Operator):
    bl_idname = "texlib.cancel_search"
    bl_label = ""
    
    
    def execute(self, context):
        thread_search = threads[THREAD_SEARCHING]
        thread_search.cancel = True
        texlib = context.scene.texlib
        
        searching_dwn = texlib.searching_download
        searching_dwn.alive = False

        return{'FINISHED'}


def load_material_items(material_items):
    material_items.clear()
    for i in last_search:
        new_item:MaterialItem = material_items.add()
        item_id =  last_search[i]["id"]
        new_item.name = item_id
        if hasattr(previews_collection, "preview_items") and item_id in previews_collection.preview_items:
            new_item.thumb = previews_collection.preview_items[item_id][3]
        else:
            new_item.thumb = lib.custom_icons["input"].icon_id

def load_per_material(file_name:str, material_item):
    item = os.path.basename(file_name)

    my_id = item.split(".")[0]
    # print(">>item",item,"file",file_name, "my_id", my_id)
    loaded = previews_collection.load(item, file_name, 'IMAGE', force_reload=True)

    previews_collection.preview_items[my_id] = (my_id, item, "", loaded.icon_id, len(previews_collection.preview_items))
    material_item.thumb = loaded.icon_id

    
def searching_material(keyword:str, context:Context):
    scene = context.scene
    txlib = scene.texlib

    thread_search = threads[THREAD_SEARCHING]

    retrieve_assets_info(keyword)
    thread_search.progress = 10
    load_material_items(txlib.material_items)

    download_previews(False, txlib.material_items)
    thread_search.progress = 90
    load_previews()
    thread_search.progress = 95


    load_material_items(txlib.material_items)
    thread_search.progress = 100

   
def load_previews():
    # print(">>>>>>>>>>>>>>>>>>>>>>> INIT TexLIB")
    dir_name = _get_preview_dir()
    files = os.listdir(dir_name)
    
    previews_collection.clear()
    preview_items = {}
    for index, item in enumerate(files):
        file = dir_name + item
        my_id = item.split(".")[0]
        # print(">>item",item,"file",file)
        loaded = previews_collection.load(item, file, 'IMAGE', force_reload=True)
        preview_items[my_id] = (my_id, item, "", loaded.icon_id, index)

    previews_collection.preview_items.update(preview_items)

def monitor_downloads():
        
    searching = False
    if THREAD_SEARCHING in threads:
        thread_search = threads[THREAD_SEARCHING]
        searching = True

    if not hasattr(bpy, 'context'):
        print("no context")
        return 2

    scn = bpy.context.scene
    txlb = scn.texlib
    downloads = txlb.downloads

    if len(downloads) == 0 and not searching:
        # print("KOSONG")
        return 2
    
    if searching:
        prog_search = thread_search.progress
        txlb.searching_download.progress = prog_search
        if thread_search.progress >= 100:
            txlb.searching_download.alive = False

        if not thread_search.is_alive():
            del threads[THREAD_SEARCHING]
    
    # print("downloadku", len(downloads))
    # for index, dwn in enumerate(downloads):
    #     print("cek aja",dwn.asset_id," | ",dwn.asset_attribute)
    
    if len(downloads):
        to_remove = []
        for index, dwn in enumerate(downloads):
            
            thread_id = _get_thread_id(dwn.asset_id, dwn.asset_attribute)
            thread = _get_thread(thread_id)
            if thread == None:
                print("thread id", thread_id, ">",dwn.asset_id,">", dwn.asset_attribute)
                extract_file(dwn.file_path)
                delete_zip(dwn.file_path)
                to_remove.append(index)

            else:
                prog =  thread.progress

                dwn.progress = prog
                if thread.progress >= 100:
                    dwn.alive = False

                if not thread.is_alive():
                    del threads[thread_id]

        for i in to_remove:
            downloads.remove(i)

    for window in bpy.context.window_manager.windows:
        # print("==============windoss ", window)
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for reg in area.regions:
                    # print("region",reg.type, "width", reg.width)
                    open_tab = reg.width > 1
                    if reg.type == "UI" and open_tab:
                        # print("redraw area", area.type, "reg", reg.type)
                        reg.tag_redraw()
                        return 0.1

    return 1.0

def extract_file(my_file):
    dir_name = os.path.dirname(my_file)
    # new_folder = os.path.basename(my_file).split('.')[0]
    # dir_name = os.path.join(dir_name, new_folder)
    print("extract "+my_file+" to "+dir_name)

    with ZipFile(my_file, 'r') as zObject:
        zObject.extractall(path=dir_name)
        return dir_name
    
# Delete the zip file
def delete_zip(file_path):
    if not os.path.exists(file_path):
        return
    try:
        os.remove(file_path)
    except Exception as e:
        print('Error while deleting zip file:', e)

def download_stream(link:str, file_name:str, thread_id:str,
                    timeout:int = 10,skipExisting:bool = False):
    # print("url = ",link, "filename", file_name)

    thread = _get_thread(thread_id)
    
    prog = 0
    with open(file_name, "wb") as f:
        try:
            response = requests.get(link, stream=True, timeout = timeout)
            # session seems to be a little bit faster
            #session = requests.Session()
            #response = session.get(link, stream=True, timeout = timeout)
            total_length = response.headers.get('content-length')
            print("total size = "+total_length)
            if not total_length:
                print('Error #1 while downloading', link, ':', "Empty Response.")
                return
            
            dl = 0
            total_length = int(total_length)
            # TODO a way for calculating the chunk size
            for data in response.iter_content(chunk_size = 4096):

                dl += len(data)
                f.write(data)
                
                prog = int(100 * dl / total_length)
                # dl_threads[0].progress = prog
                thread.progress = prog
                # print("proggg "+str(prog)+"%  "+str(dl)+"/"+str(total_length))
            # dl_threads.pop(0)
        except Exception as e:
            print('Error #2 while downloading', link, ':', e)

def download_previews(overwrite_existing:bool, material_items):
    directory = _get_preview_dir()
    if not os.path.exists(directory):
        os.mkdir(directory)
    print("download to ",directory)
    # print("asset",assets_lib)
    thread_search = threads[THREAD_SEARCHING]
    
    progress_initial = thread_search.progress
    progress_max = 90
    span = progress_max - progress_initial
    item_count = len(last_search)

    for index,ast in enumerate(last_search):
        if thread_search.cancel:
            break
        link = last_search[ast]["preview"]
        file_name = bpy.path.basename(link)
        file_name = os.path.join(directory, file_name)
        
        if not overwrite_existing and os.path.exists(file_name):
            continue
        with open(file_name, "wb") as f:
            try:
                response = requests.get(link, stream=True)
                total_length = response.headers.get('content-length')
                if not total_length:
                    print('Error #1 while downloading', link, ':', "Empty Response.")
                    return
                dl = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size = 4096):
                    dl += len(data)
                    f.write(data)                    
            except Exception as e:
                print('Error #2 while downloading', link, ':', e)
        prog = (index + 1) / item_count
        print("url = ",prog, ' | ',link,' | ', file_name)
        # refresh list
        load_per_material(file_name, material_items[index])

        thread_search.progress = (int) (progress_initial + prog * span)

def read_asset_info() -> bool:
    dir_name = _get_lib_dir()
    file_name = os.path.join(dir_name, "lib.json")

    if os.path.exists(file_name):
        file = open(file_name, 'r')
        content = file.read()
        jsn = json.loads(content)
        assets_lib.update(jsn)
        file.close()
        print("read ", content)
        return True
    return False

def retrieve_assets_info(keyword:str = '', page:int = 0, limit:int = 10):
    base_link = "https://ambientCG.com/api/v2/full_json"
    params = {
        'type': 'Material',
        'include':'imageData,downloadData',
        'limit': str(limit),
        'offset': str(limit * page) 
    }

    if keyword != '':
        params['q'] = keyword
    
    dir_name = _get_lib_dir()
    file_name = os.path.join(dir_name, "lib.json")
    file_name_ori = os.path.join(dir_name, "lib-ori.json")

    response = requests.get(base_link, params=params, verify=False)
    if not response.status_code == 200:
        print("Can't download, Code: " + str(response.status_code))
        return None
    
    assets = response.json()["foundAssets"]
    file = open(file_name, 'w')

    # assets_lib = {}
    last_search.clear()

    tex_directory = _get_textures_dir()
    
    
    for asst in assets:
        asset_obj = {}
        asset_id = asst["assetId"]
        asset_obj["id"] = asset_id
        asset_obj["preview"] = asst["previewImage"]["256-PNG"]

        zip_assets = asst["downloadFolders"]["default"]["downloadFiletypeCategories"]["zip"]["downloads"]


       

        downloads = {}
        for k in zip_assets:
            location = os.path.join(asset_id, k["attribute"])
            directory = os.path.join(tex_directory, location)

            downloads[k["attribute"]] = {
                "link" : k["downloadLink"],
                "fileName" : k["fileName"],
                "location" : directory+os.sep,
                "size" : k["size"]
            }
        asset_obj["downloads"] = downloads
        assets_lib[asset_id] = asset_obj
        last_search[asset_id] = asset_obj

    file.write(json.dumps(assets_lib))
    file.close()
    print("stored to ", file_name)
    # print("content to ", str(assets_lib))

    file_ori = open(file_name_ori, 'w')
    file_ori.write(json.dumps({"foundAssets":assets}))
    file_ori.close()

def _get_textures_dir() -> str:
    file_path = _get_lib_dir()
    retval = os.path.join(file_path, "textures") + os.sep
    if not os.path.exists(retval):
        os.mkdir(retval)
    return retval

def _get_preview_dir() -> str:
    file_path = _get_lib_dir()
    retval = os.path.join(file_path, "previews") + os.sep
    if not os.path.exists(retval):
        os.mkdir(retval)
    return retval

def _get_lib_dir() -> str:
    file_path = get_addon_filepath()
    retval = os.path.join(file_path, "library") + os.sep
    if not os.path.exists(retval):
        os.mkdir(retval)
    return retval

def _get_thread_id(asset_id:str, asset_attribute:str):
    return asset_id+"_"+asset_attribute

def _get_thread(id:str):
    if id in threads: 
        return threads[id]
    return None

classes = [DownloadThread,  MaterialItem, TexLibProps, TexLibBrowser, TexLibDownload, TexLibAddToUcupaint, TexLibCancelDownload,TEXLIB_UL_Material
            ,TexLibCancelSearch, TEXLIB_UL_Downloads]

def register():
    for cl in classes:
        bpy.utils.register_class(cl)



    Scene.texlib = PointerProperty(type= TexLibProps)

    global previews_collection
    previews_collection = bpy.utils.previews.new()
    previews_collection.preview_items = {}
    # load_previews()

    bpy.app.timers.register(monitor_downloads, first_interval=1, persistent=True)    

def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
    del bpy.types.Scene.texlib

    bpy.utils.previews.remove(previews_collection)

    if bpy.app.timers.is_registered(monitor_downloads):
        bpy.app.timers.unregister(monitor_downloads)

if __name__ == "__main__":
    register()