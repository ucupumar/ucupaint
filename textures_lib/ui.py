import bpy

from bpy.types import Panel, UIList

from .. import lib

from .properties import assets_library
from .properties import TexLibProps, MaterialItem, DownloadQueue, get_asset_lib, get_library_name

from .operators import TexLibAddToUcupaint, TexLibCancelDownload, TexLibDownload, TexLibRemoveTextureAttribute

from .downloader import texture_exist, get_thread, get_thread_id

from ..common import get_user_preferences

class TexLibBrowser(Panel):
    bl_label = "Texlib Browser"
    bl_idname = "TEXLIB_PT_Browser"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Ucupaint"

    @classmethod
    def poll(cls, context):
        return get_user_preferences().show_texlib_browser

    def draw(self, context):
        layout = self.layout
        texlib:TexLibProps = context.window_manager.ytexlib

        ass_lib = get_asset_lib(context)
        if ass_lib == None:
            # layout.label(text="Create an asset library named "+get_library_name())
            row = layout.row()
            row.alert = True
            row.operator("texlib.create_dir", icon="ERROR")
            return
        
        layout.prop(texlib, "mode_asset", expand=True)

        search_mode = texlib.mode_asset == "SEARCH"

        if search_mode:
            self.draw_search(context, texlib)
        else:
            self.draw_library(context, texlib)
        
    def draw_search(self, context, texlib:TexLibProps):
        layout = self.layout

        sel_index = texlib.search_index
        my_list = texlib.search_items

        # layout.operator("texlib.debug")

        layout.prop(texlib, "input_search")
        source_search = layout.row()
        # source_search.prop(texlib, "check_local")
        source_search.prop(texlib, "check_ambiencg")
        source_search.prop(texlib, "check_polyhaven")

        searching_dwn = texlib.searching_download
    
        if searching_dwn.alive:
            prog = searching_dwn.progress

            if prog >= 0:
                row_search = layout.row()

                if prog < 10:
                    row_search.label(text="Searching...")
                else:
                    row_search.prop(searching_dwn, "progress", slider=True, text="Retrieving thumbnails.")
                row_search.operator("texlib.cancel_search", icon="CANCEL")
                    
        # print("list", local_files_mode, ":",sel_index,"/",len(my_list))
        # print("list", local_files_mode, ":",texlib.material_index,"/",len(texlib.material_items)," | ", texlib.downloaded_material_index,"/",len(texlib.downloaded_material_items))
        if len(my_list):

            layout.separator()
            layout.label(text="Textures:")
            col_lay = layout.row()
           
            col_lay.template_list("TEXLIB_UL_Material", "material_list", texlib, "search_items", texlib, "search_index")

            if sel_index < len(my_list):
                sel_mat:MaterialItem = my_list[sel_index]
                mat_id:str = sel_mat.asset_id
                
                thumb = _get_asset_preview(mat_id)


                layout.separator()
                layout.label(text="Preview:")
                prev_box = layout.box()
                selected_mat = prev_box.column(align=True)
                selected_mat.alignment = "CENTER"
                selected_mat.template_icon(icon_value=thumb, scale=5.0)
                selected_mat.label(text=sel_mat.name)

                # print("len ", len(assets_library.keys()))
                download = assets_library[mat_id]

                layout.separator()
                layout.label(text="Attributes:")
                for d in download.attributes:
                    attribute = download.attributes[d]
                    current_asset = attribute.asset
                    # row.alignment = "LEFT"
                    total_size = current_asset.size
                    for t in attribute.textures:
                        total_size += t.size

                    ukuran = round(total_size / 1000000,2)
                    
                    check_exist:bool = texture_exist(context, mat_id, d)

                    ui_attr = layout.split(factor=0.7)

                    row = ui_attr.row()

                    row.label(text=d, )
                    # rr.label(text=d, )
                    row.label(text=str(ukuran)+ "MB")

                    thread_id = get_thread_id(mat_id, d)
                    dwn_thread = get_thread(thread_id)

                    btn_row = ui_attr.row()
                    btn_row.alignment = "RIGHT"

                    if dwn_thread != None:
                        btn_row.label(text=str(dwn_thread.progress)+"%")
                        op:TexLibCancelDownload = btn_row.operator("texlib.cancel", icon="X")
                        op.attribute = d
                        op.id = mat_id
                    else:
                        if check_exist:
                            op:TexLibAddToUcupaint = btn_row.operator("texlib.add_to_ucupaint", icon="ADD")
                            op.attribute = d
                            op.id = sel_mat.asset_id

                            op_remove:TexLibRemoveTextureAttribute = btn_row.operator("texlib.remove_attribute", icon="REMOVE")
                            op_remove.attribute = d
                            op_remove.id = sel_mat.asset_id

                        op:TexLibDownload = btn_row.operator("texlib.download", icon="IMPORT")
                        op.id = sel_mat.asset_id
                        op.attribute = d
                        op.file_exist = check_exist

            if len(texlib.downloads):
                layout.separator()
                layout.label(text="Downloads:")
                layout.template_list("TEXLIB_UL_Downloads", "download_list", texlib, "downloads", texlib, "selected_download_item")

    def draw_library(self, context, texlib:TexLibProps):
        sel_index = texlib.library_index
        my_list = texlib.library_items
        layout = self.layout

        if sel_index >= len(my_list):
            sel_index = len(my_list) - 1

        selected:MaterialItem = my_list[sel_index]
    
        layout.template_list("TEXLIB_UL_Material", "material_list", texlib, "library_items", texlib, "library_index")
        layout.operator("texlib.show_lib")

        layout.separator()
        layout.label(text="Preview:")   
        mat_name = selected.name
        prev_box = layout.box()
        selected_mat = prev_box.column(align=True)
        selected_mat.alignment = "CENTER"
        thumb = _get_asset_preview(selected.asset_id)
        selected_mat.template_icon(icon_value=thumb, scale=5.0)
        selected_mat.label(text=mat_name)

        split_names = mat_name.split("_")
        if len(split_names) > 1:
            attr = split_names[-1]

        btns = layout.row()

        op:TexLibAddToUcupaint = btns.operator("texlib.add_to_ucupaint", icon="ADD")
        op.attribute = attr
        op.id = selected.asset_id

        remove:TexLibRemoveTextureAttribute = btns.operator("texlib.remove_attribute", icon="REMOVE")
        remove.attribute = attr
        remove.id = selected.asset_id

class TEXLIB_UL_Downloads(UIList):

    def draw_item(self, context, layout, data, item:DownloadQueue, icon, active_data, active_propname, index):
        """Demo UIList."""
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            if item.alive:
                row.prop(item, "progress", slider=True, text=item.asset_id+" | "+item.asset_attribute)
                op:TexLibCancelDownload = row.operator("texlib.cancel", icon="X")  
                op.attribute = item.asset_attribute
                op.id = item.asset_id
            else:
                row.label(text="cancelling")

class TEXLIB_UL_Material(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        """Demo UIList."""

        thumb = _get_asset_preview(item.asset_id)

        row = layout.row(align=True)
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row.template_icon(icon_value = thumb, scale = 1.0)
            row.label(text=item.name)
            if item.source_type != "":
                row.label(text=item.source_type)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon_value = thumb)


classes = [
    TexLibBrowser,
    TEXLIB_UL_Material,
    TEXLIB_UL_Downloads
]

def _get_asset_preview(item_id:str):
    from .properties import previews_collection
         
    if hasattr(previews_collection, "preview_items") and item_id in previews_collection.preview_items:
        thumb = previews_collection.preview_items[item_id][3]
    else:
        thumb = lib.custom_icons["input"].icon_id
    return thumb

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)