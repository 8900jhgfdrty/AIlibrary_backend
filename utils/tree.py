from django.apps import apps

class PermissionTree:
    def __init__(self, user_object):
        self.user_object = user_object
        self.Permission = apps.get_model('api', 'Permission')  # 替换为你的app名称和模型名
        self.Menu = apps.get_model('api', 'Menu')  # 替换为你的app名称和模型名

    def build_menu_tree(self, menu, permissions_dict):
        """递归地构建菜单树，并为每个菜单项附加权限信息
        """
        children = self.Menu.objects.filter(parent_id=menu.id).distinct()
        child_list = []
        for child in children:
            if child.id in permissions_dict:  # 确保只添加有权限的子菜单
                child_permissions = {route: list(methods) for route, methods in permissions_dict.items()}
                print("看看是啥:%s"%child_permissions)
                child_list.append({
                    'title': child.title,
                    'name': child.name,
                    'icon': child.icon,
                    'permission': child_permissions  # 将权限信息挂载到子菜单上
                })

        top_menu_permissions = permissions_dict.get(menu.id, {})
        # top_menu_permissions_dict = {perm['route']: [perm['method']] for perm in top_menu_permissions}

        return {
            'title': menu.title,
            'name': menu.name,
            'icon': menu.icon,
            # 'permission': top_menu_permissions_dict if top_menu_permissions_dict else None,  # 如果没有权限则不显示
            'children': child_list if child_list else None  # 如果没有子菜单则不显示
        }
