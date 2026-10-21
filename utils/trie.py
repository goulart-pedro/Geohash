"""Trie compacta (árvore radix) para strings Geohash.

Cada aresta carrega um rótulo (substring); nós internos sem valor e com um único
filho são fundidos. Logo, para k valores armazenados existem O(k) nós, e a busca
por prefixo custa O(m) para descer + O(k) para coletar a subárvore.
"""


class _Node:
    __slots__ = ("label", "children", "items")

    def __init__(self, label=""):
        self.label = label        # rótulo da aresta que chega neste nó
        self.children = {}        # primeiro caractere -> _Node
        self.items = []           # valores cujo Geohash termina neste nó


class CompactTrie:
    def __init__(self):
        self.root = _Node()
        self._size = 0
        self.last_nodes_visited = 0

    def __len__(self):
        return self._size

    # ------------------------------------------------------------------ insert
    def insert(self, key, value):
        node = self.root
        i = 0
        n = len(key)
        while True:
            if i == n:
                node.items.append(value)
                self._size += 1
                return
            c = key[i]
            child = node.children.get(c)
            if child is None:
                new = _Node(key[i:])
                new.items.append(value)
                node.children[c] = new
                self._size += 1
                return
            label = child.label
            j = 0
            while j < len(label) and i + j < n and label[j] == key[i + j]:
                j += 1
            if j == len(label):          # aresta inteira casou: desce
                node = child
                i += j
                continue
            # casamento parcial: divide a aresta em duas
            mid = _Node(label[:j])
            child.label = label[j:]
            mid.children[child.label[0]] = child
            node.children[c] = mid
            i += j
            if i == n:
                mid.items.append(value)
            else:
                new = _Node(key[i:])
                new.items.append(value)
                mid.children[key[i]] = new
            self._size += 1
            return

    # ------------------------------------------------------------------ search
    def search_prefix(self, prefix):
        """Todos os valores cujo Geohash começa com `prefix`. O(m + k)."""
        node = self.root
        visited = 1
        i = 0
        m = len(prefix)
        while i < m:
            child = node.children.get(prefix[i])
            if child is None:
                self.last_nodes_visited = visited
                return []
            visited += 1
            label = child.label
            rem = prefix[i:]
            k = min(len(label), len(rem))
            if label[:k] != rem[:k]:
                self.last_nodes_visited = visited
                return []
            i += k          # se o prefixo acaba no meio da aresta, a subárvore inteira casa
            node = child
        result = []
        stack = [node]
        while stack:
            cur = stack.pop()
            if cur.items:
                result.extend(cur.items)
            if cur.children:
                stack.extend(cur.children.values())
                visited += len(cur.children)
        self.last_nodes_visited = visited
        return result

    # ------------------------------------------------------------------- stats
    def node_count(self):
        count = 0
        stack = [self.root]
        while stack:
            cur = stack.pop()
            count += 1
            stack.extend(cur.children.values())
        return count
