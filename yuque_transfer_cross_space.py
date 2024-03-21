"""
@Time    : 2024/3/19 15:46
@File    : 语雀转移.py

"""
import re
import httpx
import requests
import simplejson
from urllib.parse import unquote


class YuqueDocumentControl:
    source_url = ""
    source_book_id = 0
    source_domain = ""
    source_tree = {}
    source_id_format_dict = {}
    source_doc_full_path_list = []
    source_doc_full_title_path_list = []

    target_url = ""
    target_book_id = 0
    target_domain = ""
    target_tree = {}
    target_id_format_dict = {}
    target_doc_full_path_list = []
    target_doc_full_title_path_list = []
    yuque_cookies = {}

    def __init__(self, cookies, source_url, target_url):
        self.yuque_cookies = cookies
        self.source_url = source_url
        self.source_domain = source_url.split("/")[2]
        self.target_url = target_url
        self.target_domain = target_url.split("/")[2]

    def find_node(self, tree, node, with_key=False):
        """
        爸爸去哪儿啦: 找找子节点应该有的父节点
        :param tree:
        :param node:
        :param with_key:
            是否返回带文档uuid格式: {"文档uuid": {"type":..,"child":{}}}
            不带uuid: {"type":..,"child":{}}
        :return:
        """
        # 每次函数只找一层，递归寻找
        for k, v in tree.items():
            # 如果找到父uuid，这就是它爸爸
            if node == k:
                if with_key:
                    return {k: v}
                else:
                    return v
            if v["child"]:
                father = self.find_node(v["child"], node, with_key=with_key)
                if father is not None:
                    return father
        # return tree

    def print_dict_reverse(self, d, key_path="", cache_list=None, print_title=False):
        """
        递归反转输出
        :param print_title:
        :param cache_list:
        :param key_path:
        :param d:
        :param indent:
        :return:
        """
        if cache_list is None:
            cache_list = []
        """key: uuid; value: {'type': 'DOC', 'title': '「标题」', 'url': '「url上的链接」', 'child': {}}"""
        for key, value in reversed(list(d.items())):
            val = key if not print_title else value["title"]
            if value["child"]:
                self.print_dict_reverse(value["child"], f"{key_path}/{val}", cache_list, print_title)
            else:
                cache_list.append(f"{key_path}/{val}")
        return cache_list

    def get_yuque_document_tree(self, url):
        """ 访问源空间知识库与目的空间知识库主页，获取知识库的文档列表 """
        resp = requests.get(url, cookies=self.yuque_cookies, timeout=10).text
        data_json_str = re.findall("JSON.parse\(decodeURIComponent\(\"(.*?)\"\)\);", resp)
        if not data_json_str:
            print("读取首页内容后无法匹配到文档结构json数据，退出转移")
            exit()
        data_json_str = data_json_str[0]
        # 使用unquote进行URL解码
        decoded_json = unquote(data_json_str)
        data_json = simplejson.loads(decoded_json)
        # 文档数据，格式 [{}, {}]
        book_id = data_json["book"]["id"]
        core_domain = url.split("/")[2]
        request_url = f"https://{core_domain}/api/docs?book_id={book_id}"
        resp = requests.get(request_url, cookies=self.yuque_cookies, timeout=10).json()
        id_format_dict = dict()
        # print(resp)
        for item in resp["data"]:
            id_format_dict[item["id"]] = item["format"]
        toc_data = data_json["book"]["toc"]
        doc_dict = {}
        # 递归方式梳理整个节点tree
        for toc in toc_data:
            if toc["parent_uuid"] == "":
                doc_dict[toc["uuid"]] = {"type": toc["type"], "title": toc["title"], "url": toc["url"], "id": toc["id"], "child": {}}
            else:
                father = self.find_node(doc_dict, toc["parent_uuid"])
                father["child"][toc["uuid"]] = {"type": toc["type"], "title": toc["title"], "url": toc["url"], "id": toc["id"], "child": {}}
        # print(f"==> 更新文档树 总文档数 {len(toc_data)} 更新 {url} ")
        # 由后往前方式输出(先转移后的，后的也会放在后面)
        return book_id, id_format_dict, doc_dict, self.print_dict_reverse(doc_dict), self.print_dict_reverse(doc_dict, print_title=True)

    def update_yuque_projects_info(self):
        """ 更新源空间知识库信息 """
        # 更新源空间与目的空间知识库信息
        self.source_book_id, self.source_id_format_dict, self.source_tree, self.source_doc_full_path_list, self.source_doc_full_title_path_list\
            = self.get_yuque_document_tree(self.source_url)
        # 更新目的空间知识库信息
        self.target_book_id, self.target_id_format_dict, self.target_tree, self.target_doc_full_path_list, self.target_doc_full_title_path_list\
            = self.get_yuque_document_tree(self.target_url)

    def print_full_path(self, source=True):
        if source:
            for i in self.source_doc_full_title_path_list:
                print(i)
        else:
            for i in self.target_doc_full_title_path_list:
                print(i)

    def get_document_data(self, doc_type, path):
        """
        获取文档导出内容
        :param doc_type:
        :param path:
        :param source_id:
        :return:
        """
        node = self.find_node(self.source_tree, path)
        doc_url = node["url"]
        request_url = f"{self.source_url}/{doc_url}/{doc_type}?attachment=true"
        data = requests.get(request_url, cookies=self.yuque_cookies).text
        return data

    def create_catalog(self, title, father_uuid=None):
        """
        创建"目录"
        :param title:
        :param father_uuid:
        :return:
        """
        request_url = f"https://{self.target_domain}/api/catalog_nodes"
        request_headers = {"Content-Type": "application/json", "Referer": f"https://{self.target_domain}"}
        request_json = {"action": "insert", "book_id": self.target_book_id, "format": "list", "target_uuid": father_uuid, "type": "TITLE"}
        resp = requests.put(request_url, headers=request_headers, cookies=self.yuque_cookies, json=request_json).json()
        node_uuid = resp["meta"]["node_uuid"]
        request_url = f"https://{self.target_domain}/api/catalog_nodes"
        request_json = {"action": "edit", "book_id": self.target_book_id, "doc_id": None, "format": "list", "node_uuid": node_uuid, "title": title}
        resp = requests.put(request_url, headers=request_headers, cookies=self.yuque_cookies, json=request_json).json()
        node_uuid = resp["meta"]["node_uuid"]
        return node_uuid

    def upload_doc(self, doc_type, title, upload_data, father_uuid=None):
        """
        上传文档，如果是一级目录文档，直接新建；否则得加一个父uuid字段
        :param doc_type:
        :param title:
        :param upload_data:
        :param father_uuid:
        :return:
        """

        upload_type = doc_type if doc_type != "lakemind" else "lakeboard"
        webkit_form_boundary = "WebKitFormBoundary1vmkIhNww7kiuHRG"  # 上传边界标识符
        request_url = f"https://{self.target_domain}/api/import?ctoken=ovUjiLNDAB23Pc3wxuSSsN3W"
        request_headers = {"Content-Type": f"multipart/form-data; boundary=----{webkit_form_boundary}", "Referer": f"https://{self.target_domain}"}
        if not father_uuid:
            request_data = f"------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"insert_to_catalog\"\r\n\r\ntrue\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"action\"\r\n\r\nprependChild\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"book_id\"\r\n\r\n{self.target_book_id}\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"type\"\r\n\r\n{upload_type}\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"import_type\"\r\n\r\ncreate\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"filename\"\r\n\r\nfile\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{title}.{doc_type}\"\r\nContent-Type: application/octet-stream\r\n\r\n{upload_data}\r\n------{webkit_form_boundary}--\r\n"
        else:
            father_node = self.find_node(self.target_tree, father_uuid)
            father_url = father_node["url"]
            father_title = father_node["title"]
            request_data = f"------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"toc_node_uuid\"\r\n\r\n{father_uuid}\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"toc_node_url\"\r\n\r\n{father_url}\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"toc_node_title\"\r\n\r\n{father_title}\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"create_from\"\r\n\r\ndoc_toc\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"insert_to_catalog\"\r\n\r\ntrue\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"action\"\r\n\r\nprependChild\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"target_uuid\"\r\n\r\n{father_uuid}\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"book_id\"\r\n\r\n{self.target_book_id}\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"type\"\r\n\r\n{upload_type}\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"import_type\"\r\n\r\ncreate\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"filename\"\r\n\r\nfile\r\n------{webkit_form_boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{title}.{doc_type}\"\r\nContent-Type: application/octet-stream\r\n\r\n{upload_data}\r\n------{webkit_form_boundary}--\r\n"
        client = httpx.Client()
        # proxies = {
        #     'http://': 'http://localhost:8989',  # 代理1
        #     'https://': 'http://localhost:8989',  # 代理2
        # }
        # client = httpx.Client(proxies=proxies, verify=False)
        try:
            resp = client.post(request_url, headers=request_headers, cookies=self.yuque_cookies, data=request_data).json()
            result = resp["data"]["slug"]
        except:
            print(f"转移文档 {title} 失败，返回数据: {simplejson.dumps(resp)}")
            raise
        return result

    def create_doc(self, doc_type, source_title, father_uuid):
        create_type = ""
        if doc_type == "lakesheet":
            create_type = "Sheet"
        elif doc_type == "lakeboard":
            create_type = "Board"
        elif doc_type == "lake":
            create_type = "Doc"
        else:
            raise Exception("未知类型")
        request_url = f"https://{self.target_domain}/api/docs"
        request_headers = {"Content-Type": "application/json", "Referer": f"https://{self.target_domain}"}
        request_json = {
            "action": "prependChild",
            "body_draft_asl": None,
            "book_id": self.target_book_id,
            "insert_to_catalog": True,
            "slug": "",
            "status": 0,
            "target_uuid": father_uuid,
            "title": source_title,
            "type": create_type
        }
        client = httpx.Client()
        # proxies = {
        #     'http://': 'http://localhost:8989',  # 代理1
        #     'https://': 'http://localhost:8989',  # 代理2
        # }
        # client = httpx.Client(proxies=proxies, verify=False)
        resp = client.post(request_url, headers=request_headers, cookies=self.yuque_cookies, json=request_json).json()
        new_uuid = ""
        for toc in resp["toc"]:
            if toc["parent_uuid"] == father_uuid and toc["title"] == source_title and toc["type"] == "DOC":
                new_uuid = toc["sibling_uuid"]
        return new_uuid

    def transform_one_full_document(self, full_path):
        # 用来寻找的下一级文档列表树，如 /a/b/c，寻找/b则在/a的下属文档中寻找
        find_space = self.target_tree
        # 用来创建的当前文档uuid，如 /a/b/c，创建/b则需要锁定a的uuid
        father_uuid = ""
        for path in full_path[1:].split("/"):
            """ 
            拿到源节点，根据名字判断有没有同名同路径的
            没有就新建且更新目的知识库的树
            有就 """
            source_node = self.find_node(self.source_tree, path)
            source_title = source_node["title"]
            source_type = source_node["type"]
            # 看看当前层级下有没有同名路径或文档，有就用下一级文档列表作为下一步的对象，没有就新建
            find_flag = False
            for uuid, info in find_space.items():
                if source_title == info["title"]:
                    find_space = info["child"]
                    father_uuid = uuid
                    find_flag = True
                    break
            if not find_flag:
                new_uuid = ""
                # 如果是文档类型，则获取文件内容，并创建
                if source_type == "DOC":
                    # 文档有内容，就调用import导入接口；文档没内容，就直接创建，否则导入接口会报错
                    doc_type = self.source_id_format_dict[source_node["id"]]
                    doc_data = self.get_document_data(doc_type, path)
                    if doc_data:
                        print(f"=> 转移文档 {source_title}")
                        new_uuid = self.upload_doc(doc_type, source_title, doc_data, father_uuid)
                    else:
                        print(f"=> 创建文档 {source_title}")
                        new_uuid = self.create_doc(doc_type, source_title, father_uuid)
                # 如果是目录类型，就直接新建
                if source_type == "TITLE":
                    print(f"=> 新建路径  {source_title}")
                    new_uuid = self.create_catalog(source_title, father_uuid)
                # 并且更新
                self.update_yuque_projects_info()
                # 更新搜索的树
                find_space = self.find_node(self.target_tree, new_uuid, with_key=True)
                father_uuid = new_uuid
            else:
                print(f"=> 路径或文档已存在  {source_title}")

    def transform_all_document(self):
        """ 转移文档到新空间 """
        current_num = 1
        for full_path in self.source_doc_full_path_list:
            try_count = 0
            while True:  # 因语雀接口会有未响应情况，设置超时10秒、重试3次报错
                try:
                    title_full_path = ""
                    for path in full_path[1:].split("/"):
                        source_node = self.find_node(self.source_tree, path)
                        source_title = source_node["title"]
                        title_full_path += "/" + source_title
                    print(f"===========> 正在处理 {current_num}/{len(self.source_doc_full_path_list)} {title_full_path}")
                    self.transform_one_full_document(full_path)
                    current_num += 1
                    break
                except Exception as e:
                    try_count += 1
                    if try_count > 2:
                        raise


if __name__ == '__main__':
    print("===========> 语雀跨空间文档转移程序，填写源知识库、目的知识库、cookie，一键转移")
    print("=========> 如存在路径一样，可能无法识别")
    # 转移源空间知识库
    source_project = "「来源空间的知识库的链接」"
    # 转移目的空间
    target_project = "「目的空间的知识库的链接」"
    # 语雀cookies
    cookies = {"_yuque_session": "cookie中的 _yuque_session"}
    control = YuqueDocumentControl(cookies, source_project, target_project)
    control.update_yuque_projects_info()
    control.transform_all_document()



