(function (window) {
    "use strict";

    /**
     * Creates a new Model instance and hooks up the storage.
     *
     * @constructor
     * @param {object} storage A reference to the client side storage class
     */
    function Model(storage) {
        this.storage = storage;
    }

    /**
     * Creates a new todo model
     *
     * @param {string} [title] The title of the task
     * @param {function} [callback] The callback to fire after the model is created
     */
    Model.prototype.create = function (title, callback) {
        title = title || "";
        callback = callback || function () {};

        var newItem = {
            title: title.trim(),
            completed: false,
            subject: "unassigned",
        };

        this.storage.save(newItem, callback);
    };

    /**
     * Finds and returns a model in storage. If no query is given it'll simply
     * return everything. If you pass in a string or number it'll look that up as
     * the ID of the model to find. Lastly, you can pass it an object to match
     * against.
     *
     * @param {string|number|object} [query] A query to match models against
     * @param {function} [callback] The callback to fire after the model is found
     *
     * @example
     * model.read(1, func); // Will find the model with an ID of 1
     * model.read('1'); // Same as above
     * //Below will find a model with foo equalling bar and hello equalling world.
     * model.read({ foo: 'bar', hello: 'world' });
     */
    Model.prototype.read = function (query, callback) {
        var queryType = typeof query;
        callback = callback || function () {};

        if (queryType === "function") {
            callback = query;
            return this.storage.findAll(callback);
        } else if (queryType === "string" || queryType === "number") {
            query = parseInt(query, 10);
            return this.storage.find({ id: query }, callback);
        } else {
            return this.storage.find(query, callback);
        }
    };

    /**
     * Updates a model by giving it an ID, data to update, and a callback to fire when
     * the update is complete.
     *
     * @param {number} id The id of the model to update
     * @param {object} data The properties to update and their new value
     * @param {function} callback The callback to fire when the update is complete.
     */
    Model.prototype.update = function (id, data, callback) {
        this.storage.save(data, callback, id);
    };

    /**
     * 返回全清单（按存储顺序）。参考实现用它做筛选、移动与计数。
     *
     * @param {function} callback The callback to fire with the full list
     */
    Model.prototype.readAll = function (callback) {
        this.storage.findAll(callback);
    };

    /**
     * 按顺序重写整个清单（用于交换两条作业的位置）。
     *
     * @param {array} todos 新的全清单顺序
     * @param {function} callback The callback to fire after saving
     */
    Model.prototype.rewrite = function (todos, callback) {
        this.storage.saveAll(todos, callback);
    };

    /**
     * 交换两条作业在全清单中的位置。
     *
     * @param {number} idA 其中一条的 id
     * @param {number} idB 另一条的 id
     * @param {function} callback The callback to fire after saving
     */
    Model.prototype.swap = function (idA, idB, callback) {
        var self = this;
        self.storage.findAll(function (todos) {
            var ia = -1;
            var ib = -1;

            for (var i = 0; i < todos.length; i++) {
                if (todos[i].id === idA)
                    ia = i;
                if (todos[i].id === idB)
                    ib = i;
            }

            if (ia === -1 || ib === -1 || ia === ib) {
                callback.call(self, todos);
                return;
            }

            var tmp = JSON.parse(JSON.stringify(todos[ia]));
            todos[ia] = JSON.parse(JSON.stringify(todos[ib]));
            todos[ib] = tmp;

            self.storage.saveAll(todos, function () {
                callback.call(self, todos);
            });
        });
    };

    /**
     * Removes a model from storage
     *
     * @param {number} id The ID of the model to remove
     * @param {function} callback The callback to fire when the removal is complete.
     */
    Model.prototype.remove = function (id, callback) {
        this.storage.remove(id, callback);
    };

    /**
     * WARNING: Will remove ALL data from storage.
     *
     * @param {function} callback The callback to fire when the storage is wiped.
     */
    Model.prototype.removeAll = function (callback) {
        this.storage.drop(callback);
    };

    /**
     * Returns a count of all todos
     */
    Model.prototype.getCount = function (callback) {
        var todos = {
            active: 0,
            completed: 0,
            total: 0,
        };

        this.storage.findAll(function (data) {
            data.forEach(function (todo) {
                if (todo.completed)
                    todos.completed++;
                else
                    todos.active++;

                todos.total++;
            });
            callback(todos);
        });
    };

    // Export to window
    window.app = window.app || {};
    window.app.Model = Model;
})(window);
