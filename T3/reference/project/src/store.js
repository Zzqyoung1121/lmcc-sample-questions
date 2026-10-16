/* jshint eqeqeq:false */
(function (window) {
    "use strict";

    var STORAGE_KEY = "todos-lmcc";
    var ID = 1;

    // 参考实现：把原来的内存存储换成本地存储，刷新后数据仍在。
    // 只依赖 window.localStorage，不访问网络。
    var backend = {
        read: function () {
            var raw = null;
            try {
                raw = window.localStorage.getItem(STORAGE_KEY);
            } catch (e) {
                raw = null;
            }
            if (!raw)
                return { todos: [] };
            try {
                var parsed = JSON.parse(raw);
                if (!parsed || !Array.isArray(parsed.todos))
                    return { todos: [] };
                return parsed;
            } catch (e) {
                return { todos: [] };
            }
        },
        write: function (data) {
            try {
                window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
            } catch (e) {
                // 存储不可用时静默降级，不影响页面功能
            }
        },
    };

    var MemoryStorage = {
        read: backend.read,
        write: backend.write,
    };

    /**
     * Creates a new client side storage object and will create an empty
     * collection if no collection already exists.
     *
     * @param {string} name The name of our DB we want to use
     * @param {function} callback Our fake DB uses callbacks because in
     * real life you probably would be making AJAX calls
     */
    function Store(name, callback) {
        callback = callback || function () {};

        // 刷新后把 ID 推到已有数据之后，避免新条目与旧条目 ID 冲突
        var existing = MemoryStorage.read().todos;
        for (var i = 0; i < existing.length; i++) {
            if (typeof existing[i].id === "number" && existing[i].id >= ID)
                ID = existing[i].id + 1;
        }

        this._dbName = name;

        callback.call(this, MemoryStorage.read());
    }

    /**
     * Finds items based on a query given as a JS object
     *
     * @param {object} query The query to match against (i.e. {foo: 'bar'})
     * @param {function} callback     The callback to fire when the query has
     * completed running
     *
     * @example
     * db.find({foo: 'bar', hello: 'world'}, function (data) {
     *     // data will return any items that have foo: bar and
     *     // hello: world in their properties
     * });
     */
    Store.prototype.find = function (query, callback) {
        if (!callback)
            return;

        var todos = MemoryStorage.read().todos;

        callback.call(
            this,
            todos.filter(function (todo) {
                for (var q in query) {
                    if (query[q] !== todo[q])
                        return false;
                }

                return true;
            })
        );
    };

    /**
     * Will retrieve all data from the collection
     *
     * @param {function} callback The callback to fire upon retrieving data
     */
    Store.prototype.findAll = function (callback) {
        callback = callback || function () {};
        callback.call(this, MemoryStorage.read().todos);
    };

    /**
     * Will save the given data to the DB. If no item exists it will create a new
     * item, otherwise it'll simply update an existing item's properties
     *
     * @param {object} updateData The data to save back into the DB
     * @param {function} callback The callback to fire after saving
     * @param {number} id An optional param to enter an ID of an item to update
     */
    Store.prototype.save = function (updateData, callback, id) {
        var data = MemoryStorage.read();
        var todos = data.todos;

        callback = callback || function () {};

        // If an ID was actually given, find the item and update each property
        if (id) {
            for (var i = 0; i < todos.length; i++) {
                if (todos[i].id === id) {
                    for (var key in updateData)
                        todos[i][key] = updateData[key];

                    break;
                }
            }

            MemoryStorage.write(data);
            callback.call(this, todos);
        } else {
            // Generate an ID
            updateData.id = ID++;

            todos.push(updateData);
            MemoryStorage.write(data);
            callback.call(this, [updateData]);
        }
    };

    /**
     * Will remove an item from the Store based on its ID
     *
     * @param {number} id The ID of the item you want to remove
     * @param {function} callback The callback to fire after saving
     */
    Store.prototype.remove = function (id, callback) {
        var data = MemoryStorage.read();
        var todos = data.todos;

        for (var i = 0; i < todos.length; i++) {
            if (todos[i].id === id) {
                todos.splice(i, 1);
                break;
            }
        }

        MemoryStorage.write(data);
        callback.call(this, todos);
    };

    /**
     * 用给定顺序整体覆盖清单（参考实现用于交换位置）。
     *
     * @param {array} todos 新的全清单
     * @param {function} callback The callback to fire after saving
     */
    Store.prototype.saveAll = function (todos, callback) {
        callback = callback || function () {};
        MemoryStorage.write({ todos: todos });
        callback.call(this, todos);
    };

    /**
     * Will drop all storage and start fresh
     *
     * @param {function} callback The callback to fire after dropping the data
     */
    Store.prototype.drop = function (callback) {
        var data = { todos: [] };
        MemoryStorage.write(data);
        callback.call(this, data.todos);
    };

    // Export to window
    window.app = window.app || {};
    window.app.Store = Store;
})(window);
