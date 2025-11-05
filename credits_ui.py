import bpy
from bpy.app.handlers import persistent
import os, requests, time, threading, json
from bpy.props import PointerProperty, IntProperty, FloatProperty
import bpy.utils.previews
from .common import get_addon_filepath, is_bl_newer_than, is_online, get_addon_title, get_user_preferences
from . import lib

class YForceUpdateSponsors(bpy.types.Operator):
    """Force Update Sponsors"""
    bl_idname = "wm.y_force_update_sponsors"
    bl_label = "Force Update Sponsors"

    # debugging purpose
    clear_image_cache : bpy.props.BoolProperty(
        default = False,
        description = "Clear image cache",
    )

    use_dummy_users : bpy.props.BoolProperty(
        default = False,
        description = "Use dummy users",
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'clear_image_cache', text="Clear Image Cache")

        if get_user_preferences().developer_mode:
            layout.prop(self, 'use_dummy_users', text="Use Dummy Users for Testing")

    def execute(self, context):
        path = credits_path
        path_last_check = os.path.join(path, "last_check.txt") # to store last check time

        if os.path.exists(path_last_check):
            os.remove(path_last_check)

        goal_ui = context.window_manager.ypui_credits
        goal_ui.initialized = False
        goal_ui.use_dummy_users = self.use_dummy_users if get_user_preferences().developer_mode else False

        refresh_image_caches(self.clear_image_cache)

        return {'FINISHED'}

class YRefreshSponsors(bpy.types.Operator):
    """Force Refresh Sponsors"""
    bl_idname = "wm.y_force_refresh_sponsors"
    bl_label = "Force Refresh Sponsors"


    def execute(self, context):
        print_info("Force refresh sponsors...")
        path = credits_path
        path_last_check = os.path.join(path, "last_check.txt") # to store last check time

        if os.path.exists(path_last_check):
            os.remove(path_last_check)

        goal_ui = context.window_manager.ypui_credits
        goal_ui.initialized = False
        goal_ui.connection_status = 'INIT'

        return {'FINISHED'}

class YTierPagingButton(bpy.types.Operator):
    """Paging"""
    bl_idname = "wm.y_sponsor_paging"
    bl_label = "Next Page"

    is_next_button : bpy.props.BoolProperty(default=True)
    tier_index : bpy.props.IntProperty(default=0)
    max_page : bpy.props.IntProperty(default=0)

    def execute(self, context):
        goal_ui = context.window_manager.ypui_credits
        current_page = goal_ui.page_tiers[self.tier_index]
        if self.is_next_button:
            current_page += 1
            if self.max_page > 0 and current_page >= self.max_page:
                current_page = self.max_page - 1
        else:
            current_page -= 1
            if current_page < 0:
                current_page = 0
        goal_ui.page_tiers[self.tier_index] = current_page

        return {'FINISHED'}
    
class YCollaboratorPagingButton(bpy.types.Operator):
    """Paging"""
    bl_idname = "wm.y_collaborator_paging"
    bl_label = "Next Page"

    is_next_button : bpy.props.BoolProperty(default=True)
    max_page : bpy.props.IntProperty(default=0)

    def execute(self, context):
        goal_ui = context.window_manager.ypui_credits
        current_page = goal_ui.page_collaborators
        if self.is_next_button:
            current_page += 1
            if self.max_page > 0 and current_page >= self.max_page:
                current_page = self.max_page - 1
        else:
            current_page -= 1
            if current_page < 0:
                current_page = 0
        goal_ui.page_collaborators = current_page

        return {'FINISHED'}
    
class YSponsorPopover(bpy.types.Panel):
    bl_idname = "NODE_PT_ysponsor_popover"
    bl_label = get_addon_title() + " Sponsor Menu"
    bl_description = get_addon_title() + " Sponsor Menu"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = 15

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout
        goal = collaborators.sponsorships
        one_time_total = 0
        recurring_total = 0
        print_info("Checking one-time sponsors...", len(collaborators.sponsors))
        for sp in collaborators.sponsors.values():
            if sp["one_time"]:
                one_time_total += sp["amount"]
            else:
                recurring_total += sp["amount"]
        
        if one_time_total > 0:
            # layout.label(text=f"One-time sponsors this month: ${one_time_total:.2f}")
            # layout.separator()
            print_info("One-time sponsors total this month: $" + str(one_time_total))
        
        if recurring_total > 0:
            # layout.label(text=f"Recurring sponsors total: ${recurring_total:.2f}")
            # layout.separator()
            print_info("Recurring sponsors total: $" + str(recurring_total))

        desc = goal.get('description', '')

        daily_row = layout.row()
        daily_row.label(text="Only counting recurring sponsors (updated daily).")
        daily_row.operator('wm.y_force_update_sponsors', text="", icon='FILE_REFRESH')

        layout.separator()
        
        row_quote = layout.row()
        char_per_line = 40
        split_desc = desc.split(' ')
        current_text = '"'
        
        maintaner = goal.get('maintainer')
        user_maintaner = collaborators.contributors.get(maintaner, None)
        maintainer_icon = user_maintaner['thumb'] if user_maintaner else 0
        if maintainer_icon:
            row_quote.template_icon(icon_value = maintainer_icon, scale = 3.0)
        col = row_quote.column(align=True)
        for d in split_desc:
            if len(current_text + d) > char_per_line: # rough estimate
                col.label(text=current_text)
                current_text = ''
            current_text += d + ' '
        col.label(text=current_text+"\"")
        col.label(text="~ "+maintaner)

class YSponsorProp(bpy.types.PropertyGroup):
    progress : FloatProperty(
        default = 0.0,
        min = 0.0,
        max = 100.0,
        description = 'Only counting recurring sponsors',
        subtype = 'PERCENTAGE'
    )

    expand_tiers : bpy.props.BoolVectorProperty(
        name = "Expand Tiers",
        description = "Expand Tiers List",
        size = 8, # cannot be dynamic
    )

    page_tiers : bpy.props.IntVectorProperty(
        name = "Page Tiers",
        description = "Page Tiers",
        size = 8, # cannot be dynamic
    )

    page_collaborators : IntProperty(
        default = 0)

    expand_description : bpy.props.BoolProperty(
        default = False,
        description = get_addon_title() + "'s sponsor is updated daily",
    )

    initialized : bpy.props.BoolProperty(
        default = False,
    )

    expanded : bpy.props.BoolProperty(
        default = False,
    )

    connection_status : bpy.props.EnumProperty(
        name = 'connection status',
        items = (
            ('INIT', "INIT", 'Initial'),
            ('REQUESTING', "REQUESTING", 'Requesting'),
            ('SUCCESS', "SUCCESS", 'Success'),
            ('FAILED', 'FAILED', "Failed")
        ),
        default='INIT'
    )

    # debugging purpose
    use_dummy_users : bpy.props.BoolProperty(
        default = False,
        description = "Use dummy users",
    )

class VIEW3D_PT_YPaint_support_ui(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_ypaint_support_ui"
    bl_label = "Support " + get_addon_title()
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    # bl_region_type = 'UI'
    bl_region_type = 'WINDOW'
    bl_ui_units_x = 13

    # bl_category = get_addon_title()
    # bl_options = {'DEFAULT_CLOSED'} 

    def draw_multiline(self, layout, text:str, panel_width:int):
        all_desc = text.split(' ')
        column = layout.column(align=True)
        current_text = ''
        for d in all_desc:
            if len(current_text + d) > panel_width // 15: # rough estimate
                column.label(text=current_text)
                current_text = ''
            current_text += d + ' '
        column.label(text=current_text)

    def draw_expanding_title(self, layout, expand, object, prop_name, title):

        icon = 'DOWNARROW_HLT' if expand else 'RIGHTARROW'
        row = layout.row(align=True)
        rrow = row.row(align=True)

        if is_bl_newer_than(2, 80):
            rrow.alignment = 'LEFT'
            rrow.scale_x = 0.95
            rrow.prop(object, prop_name, emboss=False, text=title, icon=icon)
        else:
            rrow.prop(object, prop_name, emboss=False, text='', icon=icon)
            rrow.label(text=title)

        return row

    def draw_tier_title(self, layout, expand, object, prop_name, title, index_prop, icon_val):

        icon = 'DOWNARROW_HLT' if expand else 'RIGHTARROW'
        row = layout.row(align=True)
        rrow = row.row(align=True)

        if is_bl_newer_than(2, 80):
            rrow.alignment = 'LEFT'
            rrow.scale_x = 0.95
            rrow.prop(object, prop_name, index=index_prop, emboss=False, text='', icon=icon)
            rrow.prop(object, prop_name, index=index_prop, text=title, icon_value=lib.get_icon(icon_val, 'REC'), emboss=False)
        else:
            rrow.prop(object, prop_name, index=index_prop, emboss=False, text='', icon=icon)
            # rrow.label(text=title)

        return row

    def draw_header_preset(self, context):
        goal_ui = context.window_manager.ypui_credits
        if not goal_ui.expanded:
            layout = self.layout
            row = layout.row(align=True)

            url = collaborators.sponsorships.get('url', collaborators.default_url)
            row.operator('wm.url_open', text="Donate Us", icon='FUND').url = url
            if get_user_preferences().developer_mode:
                row.operator('wm.y_force_update_sponsors', text="", icon='FILE_REFRESH')

        goal_ui.expanded = False


    def draw_item(self, layout, icon, label, url = '', scale_icon:float = 3.0, horizontal_mode:bool = True):
        if horizontal_mode:
            row = layout.row(align=True)
            row.alignment = 'LEFT'
            if scale_icon != 0.0:
                row.template_icon(icon_value = icon, scale = scale_icon)
                btn_row = row.row(align=True)
                btn_row.scale_y = scale_icon
                btn_url = btn_row.operator('wm.url_open', text=label, emboss=False, )
                btn_url.url = url
            else:
                row.label(text=label)
            
        else:
            col = layout.column(align=True)
            col.template_icon(icon_value = icon, scale = scale_icon)
            col.operator('wm.url_open', text=label, emboss=False).url = url

    def draw_empty_member(self, layout, url, scale_icon:float = 3.0, horizontal_mode:bool = True):

        content = 'No sponsors yet, be the first one!'

        if horizontal_mode:
            row = layout.row(align=True)
            if scale_icon != 0.0:
                row.alignment = 'LEFT'
                row.template_icon(icon_value = collaborators.empty_pic, scale = scale_icon)
                btn_row = row.row(align=True)
                btn_row.scale_y = scale_icon
                btn_url = btn_row.operator('wm.url_open', text=content, emboss=False, )
                btn_url.url = url
            else:
                row.label(text=content)
        else:
            col = layout.column(align=True)
            row = col.row(align=True)
            row.alignment = 'LEFT'
            row.template_icon(icon_value = collaborators.empty_pic, scale = scale_icon)

            row = col.row(align=True)
            row.alignment = 'LEFT'
            row.scale_x = 0.95
            row.operator('wm.url_open', text=content, emboss=False).url = url


    def draw_tier_members(self, panel_width, goal_ui, layout, title:str, icon_val, tier_index:int, per_column:int = 3, current_page:int = 0, per_page_item:int = 4, scale_icon:float = 3.0, horizontal_mode:bool = True):
        
        filtered_items = list()

        for item in collaborators.sponsors.values():
            if item['tier'] != tier_index:# or not item['public']:
                continue
            filtered_items.append(item)

        member_count = len(filtered_items)

        stripped_title = ''.join(c for c in title if ord(c) < 128)
        stripped_title = stripped_title.strip()

        text_object = stripped_title
        if member_count > 0:
            text_object += ' ('+str(member_count)+')'

        expand = goal_ui.expand_tiers[tier_index]
        title_row = self.draw_tier_title(layout, expand, goal_ui, 'expand_tiers', text_object, tier_index, icon_val)
        paging_layout = title_row.row(align=True)
        paging_layout.alignment = 'RIGHT'

        if per_page_item < per_column:
            per_page_item = per_column

        if expand:
            
            row = layout.row(align=True)
            row.label(text='', icon='BLANK1')
            box = row.box()
            if member_count == 0:
                url = collaborators.sponsorships.get('url', "")
                col_box = box.column(align=True)
                self.draw_empty_member(col_box, url, scale_icon, horizontal_mode)
            else:
                grid = box.grid_flow(row_major=True, columns=per_column, even_columns=True, even_rows=True, align=True)

                missing_column = per_column - (per_page_item % per_column)
                counter_member = 0
                paged_items = filtered_items[current_page * per_page_item : (current_page + 1) * per_page_item]

                for cl, item in enumerate(paged_items):
                    counter_member += 1
                    thumb = item['thumb']
                    if not thumb:
                        thumb = collaborators.loading_pic

                    id = item["name"]
                    if id == '':
                        id = item['id'].strip()
                    if item['one_time']:
                        if horizontal_mode:
                            id +=  "*"
                        else:
                            id =  "*" + id
                    self.draw_item(grid, thumb, id, item["url"], scale_icon, horizontal_mode)

                if missing_column != per_column:
                    for i in range(missing_column):
                        self.draw_item(grid, collaborators.default_pic, '', '', scale_icon, horizontal_mode)

            if member_count > per_page_item:

                prev = paging_layout.operator('wm.y_sponsor_paging', text='', icon='TRIA_LEFT')
                prev.is_next_button = False
                prev.tier_index = tier_index
                prev.max_page = (member_count + per_page_item - 1) // per_page_item

                paging_layout.label(text=str(current_page+1)+'/'+str(prev.max_page))

                next = paging_layout.operator('wm.y_sponsor_paging', text='', icon='TRIA_RIGHT')
                next.is_next_button = True
                next.tier_index = tier_index
                next.max_page = prev.max_page
                
        # paging_layout.separator()
        # paging_layout.popover("NODE_PT_ysponsor_popover", text='', icon='INFO')

    def draw(self, context):

        region = context.region
        panel_width = region.width

        layout = self.layout

        row = layout.row()
        row.alignment = 'CENTER'
        row.label(text='Support '+get_addon_title()+'!', icon='ARMATURE_DATA')

        goal = collaborators.sponsorships
        goal_ui = context.window_manager.ypui_credits

        url_donation = collaborators.default_url

        if goal and 'targetValue' in goal:
            url_donation = goal.get('url', url_donation)

            row_title = layout.row(align=True)
            row_title.alignment = 'CENTER'
            row_title.label(text= get_addon_title() + "'s goal : $" + str(goal['targetValue']) + "/month")

            # paging_layout = row_title.row(align=True)
            # paging_layout.alignment = 'RIGHT'
            # paging_layout.popover("NODE_PT_ysponsor_popover", text='', icon='QUESTION')
            
            target = goal['targetValue']

            donation = 0.0
            for i in collaborators.sponsors.values():
                if not i['one_time']:
                    donation += i['amount']

            percentage = 100 * donation / target

            goal_ui.progress = percentage

            progress_row = layout.row(align=True)
            progress_row.prop(goal_ui, 'progress', text='$'+str(donation), slider=True)
            #progress_row.separator()
            progress_row.popover("NODE_PT_ysponsor_popover", text='', icon='QUESTION')

            

        don_col = layout.column(align=True)
        don_col.scale_y = 1.5
        don_col.operator('wm.url_open', text="Become a Sponsor", icon='FUND').url = url_donation

        check_contributors(goal_ui)

        if is_online() and 'tiers' in goal and goal_ui.connection_status != "REQUESTING":
            layout.separator()
            layout.label(text="Our Sponsors :", icon='HEART')

            tiers = goal.get('tiers', [])
            if tiers:
                for tier in reversed(tiers):
                    idx = tiers.index(tier)

                    scale_icon = tier.get('scale', 3)
                    horizontal_mode = tier.get('horizontal', True)
                    # per_column_width = tier.get('per_item_width', 200)
                    # # NOTE: HACK: Older blender need smaller width to make width look the same with newer blenders
                    # if not is_bl_newer_than(4, 2):
                    #     per_column_width -= 30
                    # per_column_width = int(per_column_width * context.preferences.system.ui_scale)

                    column_count = tier.get('column_num', 1)
                    if column_count <= 0:
                        column_count = 1

                    self.draw_tier_members(panel_width, goal_ui, layout, tier['name'], tier['icon_value'], idx, column_count, goal_ui.page_tiers[idx], tier['per_page_item'], scale_icon, horizontal_mode)

            # check one time sponsor exist and expanded
            for item in collaborators.sponsors.values():
                # if item['one_time']:
                if item['one_time'] and item['public']:
                    tier = item['tier']
                    if goal_ui.expand_tiers[tier]:
                        layout.separator()
                        layout.label(text="* One-time sponsors")
                        break
        elif is_online():
            if goal_ui.connection_status == "REQUESTING":
                layout.label(text="Loading data...", icon='TIME')
            elif goal_ui.connection_status == "FAILED":
                layout.label(text="Failed to load data.", icon='ERROR')
                layout.operator('wm.y_force_refresh_sponsors', text='Reload sponsors', icon='FILE_REFRESH')
            else:
                # layout.label(text=goal_ui.connection_status, icon='ERROR')
                pass

        else:
            layout.label(text="No internet access, can't load sponsors.", icon='ERROR')

        goal_ui.expanded = True

        if get_user_preferences().developer_mode:
            layout.operator('wm.y_force_update_sponsors', text="Force Update Sponsors", icon='FILE_REFRESH')

def print_info(*args):
    if get_user_preferences().developer_mode:
        print(*args)

def print_error(*args):
    if get_user_preferences().developer_mode:
        print("ERROR:", *args)

def refresh_image_caches(force_reload:bool = False):

    path = credits_path
    folders = os.path.join(path, "icons", "contributors")
    if not os.path.exists(folders):
        os.makedirs(folders)

    is_expired = False

    path_last_check = os.path.join(path, "last_check_images.txt") # to store last check time
    current_time = time.time()

    if not force_reload:

        if os.path.exists(path_last_check):
            with open(path_last_check, "r", encoding="utf-8") as f:
                content_last_check = f.read().strip()
                
                # convert to float
                try:
                    last_check = float(content_last_check)
                except:
                    last_check = 0.0
                

                span_time = current_time - last_check
                # if last check more than a month ago, reload
                if span_time > 24 * 60 * 60 * 30:
                    is_expired = True
        else:
            is_expired = True
    else:
        is_expired = True

    if is_expired:
        with open(path_last_check, "w", encoding="utf-8") as f:
            f.write(str(current_time))
            
        # remove all images in folder 
        for f in os.listdir(folders):
            file_path = os.path.join(folders, f)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                print_info("Error removing file " + file_path + ": " + str(e))

def load_preview(key:str, file_name:str):
    if key in previews_users:
        img = previews_users[key]
    else:
        img = previews_users.load(key, file_name, 'IMAGE', True)
    return img

def check_contributors(goal_ui: YSponsorProp):
    if is_online():
        if not goal_ui.initialized: # first time init
            goal_ui.initialized = True
            print_info("first time init, loading contributors...")

            load_thread = threading.Thread(target=load_contributors, args=(goal_ui,))
            load_thread.start()
        else:
            load_expanded_images(goal_ui)
    elif goal_ui.initialized:
        goal_ui.initialized = False

def load_local_contributors():
    path = credits_path
    path_contributors = os.path.join(path, "contributors.csv")

    content = ""
    # read file if exists
    if os.path.exists(path_contributors):
        with open(path_contributors, "r", encoding="utf-8") as f:
            content = f.read()

    folders = os.path.join(path, "icons", "contributors")

    collaborators.contributors.clear()
    if content != "":
        skip_header = True
        for line in content.strip().splitlines():
            if skip_header:
                skip_header = False
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 3:
                contributor = {
                    'id': parts[0],
                    'name': parts[1],
                    'url': parts[2],
                    'image_url': parts[3],
                    'thumb': None
                }
                file_name = folders+os.sep+contributor['id']+'.png'
                if os.path.exists(file_name):
                    contributor['thumb'] = load_preview(contributor['id'], file_name).icon_id
                collaborators.contributors[contributor['id']] = contributor

def is_valid_file(path:str)->bool:
    try:
        return os.path.exists(path) and os.path.isfile(path) and os.stat(path).st_size > 0
    except:
        return False
    
def load_contributors(goal_ui: YSponsorProp):    

    path = credits_path
    if not os.path.exists(path):
        os.makedirs(path)

    path_last_check = os.path.join(path, "last_check.txt") # to store last check time

    current_time = time.time()

    reload_contributors = False
    if is_valid_file(path_last_check):
        with open(path_last_check, "r", encoding="utf-8") as f:
            content_last_check = f.read().strip()
            
            # convert to float
            try:
                last_check = float(content_last_check)
            except:
                last_check = 0.0
            

            span_time = current_time - last_check
            # if last check more than a day ago, reload
            if span_time > 24 * 60 * 60:
                reload_contributors = True
            else:
                # format span in hours
                span_hours = span_time / 3600
                format_last_check = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_check))
                print_info('Last check was '+'{:0.2f}'.format(span_hours)+' hours ago. Checked at '+str(format_last_check)+'. Not reloading contributors.')
    else:
        reload_contributors = True       


    path_contributors = os.path.join(path, "contributors.csv")
    content = ""

    # read file if exists
    if is_valid_file(path_contributors):
        with open(path_contributors, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        reload_contributors = True

    path_sponsors = os.path.join(path, "sponsors.csv")
    content_sponsors = ""

    if is_valid_file(path_sponsors):
        with open(path_sponsors, "r", encoding="utf-8") as f:
            content_sponsors = f.read()
    else:
        reload_contributors = True

    path_sponsorship_goal = os.path.join(path, "credits.json")
    content_sponsorship_goal = ""

    if is_valid_file(path_sponsorship_goal):
        with open(path_sponsorship_goal, "r", encoding="utf-8") as f:
            content_sponsorship_goal = f.read()
            settings = json.loads(content_sponsorship_goal)
            collaborators.sponsorships = settings["sponsorships"]
            collaborators.contributor_settings = settings.get("contributors", {})
    else:
        reload_contributors = True

    if reload_contributors and is_online():
        timeout_seconds = 10
        goal_ui.connection_status = "REQUESTING"
        data_url = "https://raw.githubusercontent.com/ucupumar/ucupaint-wiki/master/data/"
        
        try:
            
            # test_error = True

            # if test_error:
            #     # delay x seconds
            #     time.sleep(5)
            #     # Manual trigger exception for testing
            #     raise requests.exceptions.ConnectionError("Manual exception triggered for testing purposes")
            print_info("Reloading contributors...")
            response = requests.get(data_url + "contributors.csv", timeout=timeout_seconds)
            if response.status_code == 200:
                content = response.text
                print_info("Response:" + content)

                with open(path_contributors, "w", encoding="utf-8") as f:
                    f.write(content)

            print_info("Reloading sponsors...")
            response = requests.get(data_url + "sponsors.csv", timeout=timeout_seconds)
            if response.status_code == 200:
                content_sponsors = response.text
                print_info("Response:", content_sponsors)
                with open(path_sponsors, "w", encoding="utf-8") as f:
                    f.write(content_sponsors)

            print_info("Reloading sponsorship goal..." + data_url + "credits.json")
            response = requests.get(data_url + "credits.json", timeout=timeout_seconds)
            if response.status_code == 200:
                content_sponsorship_goal = response.text
                print_info("Response credits:" + content_sponsorship_goal)
                with open(path_sponsorship_goal, "w", encoding="utf-8") as f:
                    f.write(content_sponsorship_goal)
                settings = json.loads(content_sponsorship_goal)
                collaborators.sponsorships = settings["sponsorships"]
                collaborators.contributor_settings = settings.get("contributors", {})

            current_time = time.time()
            with open(path_last_check, "w", encoding="utf-8") as f:
                f.write(str(current_time))

            goal_ui.connection_status = "SUCCESS"
        except requests.exceptions.ReadTimeout:
            print_info("timeout request")
            reload_contributors = False
            goal_ui.connection_status = "FAILED"
        except requests.exceptions.ConnectionError:
            print_info("connection error")
            reload_contributors = False
            goal_ui.connection_status = "FAILED"
    else:
        goal_ui.connection_status = "FAILED"
        reload_contributors = False

    print_info("cont status: " + goal_ui.connection_status)

    collaborators.contributors.clear()
    skip_header = True
    for line in content.strip().splitlines():
        if skip_header:
            skip_header = False
            continue
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 3:
            contributor = {
                'id': parts[0],
                'name': parts[1],
                'url': parts[2],
                'image_url': parts[3],
                'thumb': None
            }
            collaborators.contributors[contributor['id']] = contributor

    collaborators.sponsors.clear()
    skip_header = True
    for line in content_sponsors.strip().splitlines():
        if skip_header:
            skip_header = False
            continue
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 6:
            sponsor = {
                'id': parts[0],
                'name': parts[1],
                'url': parts[2],
                'image_url': parts[3],
                'amount': float(parts[5]) if parts[5] != '' else 0.0,
                'one_time' : parts[6] == 'True',
                'tier': int(parts[7]),
                'public': parts[8] == 'True',
                
                'thumb': None
            }
            collaborators.sponsors[sponsor['id']] = sponsor
            print_info("Loaded sponsor " + sponsor['id'] + " = " + str(sponsor))
    
    # expand top 2 tiers that have members
    expanding_top_tier = 2 # todo : from settings
    # tier setup
    tiers = collaborators.sponsorships.get('tiers', [])

    # reset expand
    for i in goal_ui.expand_tiers:
        i = False

    total_tiers = len(tiers)
    for idx in range(total_tiers):
        i = total_tiers - 1 - idx
        if expanding_top_tier > 0:
            # check member count 
            member_count = 0
            for item in collaborators.sponsors.values():
                if item['tier'] == i and item['public']:
                    member_count += 1
            if member_count > 0:
                goal_ui.expand_tiers[i] = True
                expanding_top_tier -= 1

    refresh_image_caches()

    refresh_ui()

    if get_user_preferences().developer_mode:
        # extra dummy
        show_extra_dummy = goal_ui.use_dummy_users
        empty_all_sponsors = False

        if show_extra_dummy:
            tiers = collaborators.sponsorships.get('tiers', [])
            tier_count = len(tiers)

            dummy_multiplier = 3

            for m in range(dummy_multiplier):
                for i, contributor in enumerate(collaborators.contributors.values()):
                    random_num = hash(contributor['id']) % 1000

                    new_contributor = contributor.copy()

                    new_contributor['tier'] = i % tier_count
                    new_contributor['one_time'] = True if (random_num % 2) == 0 else False
                    new_contributor['public'] = True
                    new_contributor['amount'] = ((random_num % 20) + 1) * (new_contributor['tier'] + 1) * 5
                    new_contributor['id'] = contributor['id'] + str(m)

                    new_contributor['name'] = new_contributor['id']
                    collaborators.sponsors[new_contributor['id']] = new_contributor

                    print_info("Added dummy sponsor " + new_contributor['id'] + " = " + str(new_contributor))
        elif empty_all_sponsors:
            collaborators.sponsors.clear()

    print_info("loaded contributors and sponsors.")
    load_expanded_images(goal_ui)

def load_expanded_images(goal_ui: YSponsorProp):
    if collaborators.load_thread and collaborators.load_thread.is_alive():
        return

    cont_setting = collaborators.contributor_settings

    current_page_contributors = goal_ui.page_collaborators
    per_page_item_contributors = cont_setting.get('per_page_item', 12)

    paged_contributors = list(collaborators.contributors.values())[current_page_contributors*per_page_item_contributors:(current_page_contributors+1)*per_page_item_contributors]
    size_icon_contributor = cont_setting.get('icon_size', 0)

    to_load_users = []
    
    path = credits_path
    folders = os.path.join(path, "icons", "contributors")
    if not os.path.exists(folders):
        os.makedirs(folders)

    for c in paged_contributors:
        if c['thumb'] is None:
            file_name = folders + os.sep + c['id'] + '.png'
            link = c['image_url'] + "&s=" + str(size_icon_contributor)
            id = c['id']
            to_load_users.append( (link, file_name, id) )

    tiers = collaborators.sponsorships.get('tiers', [])

    for i in range(len(tiers)):
        tier = tiers[i]
        if tier.get('icon_size', 0) <= 0 or not goal_ui.expand_tiers[i]:
            continue

        current_page = goal_ui.page_tiers[i]
        per_page_item = tier.get('per_page_item', 4)
        paged_sponsors = [s for s in collaborators.sponsors.values() if s['tier'] == i and s['public']]
        paged_sponsors = paged_sponsors[current_page*per_page_item:(current_page+1)*per_page_item]

        size_icon_sponsor = tier.get('icon_size', 0)
        for sp in paged_sponsors:
            if sp['thumb'] is None:
                link = sp['image_url'] + "&s=" + str(size_icon_sponsor)
                file_name = folders + os.sep + sp['id'] + '.png'
                id = sp['id']
                to_load_users.append( (link, file_name, id) )

    print_info("to load images:", len(to_load_users))
    if len(to_load_users) > 0:
        links = [t[0] for t in to_load_users]
        file_names = [t[1] for t in to_load_users]
        ids = [t[2] for t in to_load_users]

        collaborators.load_thread = threading.Thread(target=download_stream, args=(links,file_names,ids, 20))
        collaborators.load_thread.start()

def download_stream(links, file_names, ids, timeout:int = 10):
    print_info("Downloading " + str(len(links)) + " images...")
    for idx, file_name in enumerate(file_names):
        # check if file exists
        if os.path.exists(file_name):
            print_info("exists", file_name)
        elif is_online():
            link = links[idx]
            with open(file_name, "wb") as f:
                try:
                    response = requests.get(link, stream=True, timeout = timeout)
                    total_length = response.headers.get('content-length')
                    # print_info("total size = "+total_length)
                    if not total_length:
                        print_info('Error #1 while downloading ' + link + ': Empty Response.')
                        return
                    
                    dl = 0
                    total_length = int(total_length)
                    # TODO a way for calculating the chunk size
                    for data in response.iter_content(chunk_size = 4096):

                        dl += len(data)
                        f.write(data)
                except Exception as e:
                    print_info('Error #2 while downloading ' + link + ': ' + str(e))
        else:
            continue

        k = ids[idx]
        img = load_preview(k, file_name)
        if k in collaborators.contributors:
            collaborators.contributors[k]['thumb'] = img.icon_id
        if k in collaborators.sponsors:
            collaborators.sponsors[k]['thumb'] = img.icon_id
        
        refresh_ui()
        
    collaborators.load_thread = None

def refresh_ui():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for reg in area.regions:
                    open_tab = reg.width > 1
                    if reg.type == "UI" and open_tab:
                        reg.tag_redraw()
                    # Add refresh for popover region
                    if reg.type == "WINDOW":
                        reg.tag_redraw()

classes = [
    VIEW3D_PT_YPaint_support_ui,
    YSponsorProp,
    YTierPagingButton,
    YSponsorPopover,
    YForceUpdateSponsors,
    YRefreshSponsors,
    YCollaboratorPagingButton
]

class Collaborators:
    default_pic = None
    empty_pic = None
    contributors = {}
    sponsors = {}
    sponsorships = {}
    contributor_settings = {}

def get_collaborators():
    return collaborators

@persistent
def check_contributors_on_load(scn):
    goal_ui = bpy.context.window_manager.ypui_credits
    check_contributors(goal_ui)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    global previews_users
    global collaborators
    global credits_path

    credits_path = os.path.join(get_addon_filepath(), "credits")
    icon_path = os.path.join(get_addon_filepath(), "icons")

    previews_users = bpy.utils.previews.new()
    collaborators = Collaborators()

    blank_path = os.path.join(icon_path, "blank.png")
    blank_img = load_preview('blank', blank_path)
    collaborators.default_pic = blank_img.icon_id

    empty_path = os.path.join(icon_path, "empty.png")
    empty_img = load_preview('empty', empty_path)
    collaborators.empty_pic = empty_img.icon_id

    loading_path = os.path.join(icon_path, "loading.png")
    loading_img = load_preview('loading', loading_path)
    collaborators.loading_pic = loading_img.icon_id

    collaborators.contributors = {}
    collaborators.sponsors = {}
    collaborators.sponsorships = {}

    collaborators.load_thread = None
    collaborators.default_url = "https://github.com/sponsors/ucupumar"
    collaborators.default_maintainer = "ucupumar"
    collaborators.default_contributors_url = 'https://github.com/ucupumar/ucupaint/graphs/contributors'

    load_local_contributors()

    bpy.types.WindowManager.ypui_credits = PointerProperty(type=YSponsorProp)

    ui_sp = bpy.context.window_manager.ypui_credits
    ui_sp.initialized = False

    if is_bl_newer_than(2, 80):
        check_contributors(ui_sp)

        bpy.app.handlers.load_post.append(check_contributors_on_load)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.WindowManager.ypui_credits

    global previews_users

    bpy.utils.previews.remove(previews_users)
    previews_users = None

    if is_bl_newer_than(2, 80):
        bpy.app.handlers.load_post.remove(check_contributors_on_load)
