(function (window) {
    "use strict";

    /**
     * Takes a model and view and acts as the controller between them
     *
     * @constructor
     * @param {object} model The model instance
     * @param {object} view The view instance
     */
    function Controller(model, view) {
        var self = this;
        self.model = model;
        self.view = view;

        self.view.bind("newTodo", function (title) {
            self.addItem(title);
        });

        self.view.bind("itemEdit", function (item) {
            self.editItem(item.id);
        });

        self.view.bind("itemEditDone", function (item) {
            self.editItemSave(item.id, item.title);
        });

        self.view.bind("itemEditCancel", function (item) {
            self.editItemCancel(item.id);
        });

        self.view.bind("itemRemove", function (item) {
            self.removeItem(item.id);
        });

        self.view.bind("itemToggle", function (item) {
            self.toggleComplete(item.id, item.completed);
        });

        self.view.bind("removeCompleted", function () {
            self.removeCompletedItems();
        });

        self.view.bind("toggleAll", function (status) {
            self.toggleAll(status.completed);
        });

        // 参考实现新增：行内科目变更、顶部科目筛选、上移 / 下移
        self.subjectFilter = "all";

        self.view.bind("itemSubject", function (item) {
            self.changeSubject(item.id, item.subject);
        });

        self.view.bind("subjectFilter", function (value) {
            self.subjectFilter = value;
            self._filter(true);
        });

        self.view.bind("itemMoveUp", function (item) {
            self.moveItem(item.id, -1);
        });

        self.view.bind("itemMoveDown", function (item) {
            self.moveItem(item.id, 1);
        });
    }

    /**
     * Loads and initialises the view
     *
     * @param {string} '' | 'active' | 'completed'
     */
    Controller.prototype.setView = function (locationHash) {
        var route = locationHash.split("/")[1];
        var page = route || "";
        this._updateFilterState(page);
    };

    /**
     * An event to fire on load. Will get all items and display them in the
     * todo-list
     */
    /**
     * 全清单（按存储顺序）。筛选、移动、计数都基于它。
     *
     * @param {function} callback The callback to fire with the full list
     */
    Controller.prototype._readAll = function (callback) {
        this.model.readAll(callback);
    };

    /**
     * 当前筛选条件下可见的条目（保持全清单顺序）。
     *
     * @param {array} todos 全清单
     * @returns {array} 可见条目
     */
    Controller.prototype._visible = function (todos) {
        var self = this;
        var route = self._activeRoute;

        return todos.filter(function (item) {
            if (route === "Active" && item.completed)
                return false;
            if (route === "Completed" && !item.completed)
                return false;
            if (self.subjectFilter !== "all" && (item.subject || "unassigned") !== self.subjectFilter)
                return false;
            return true;
        });
    };

    /**
     * 渲染当前可见条目，并同步移动按钮的边界禁用状态。
     */
    Controller.prototype.showEntries = function () {
        var self = this;

        self._readAll(function (todos) {
            var visible = self._visible(todos);

            self.view.render("showEntries", visible);
            self.view.render("updateMoveButtons", visible);
        });
    };

    // 兼容上游调用点
    Controller.prototype.showAll = function () { this.showEntries(); };
    Controller.prototype.showActive = function () { this.showEntries(); };
    Controller.prototype.showCompleted = function () { this.showEntries(); };

    /**
     * 修改某一条的科目。只改这一条，其余（标题、完成情况、顺序）不变。
     *
     * @param {number} id 条目 id
     * @param {string} subject 新科目
     */
    Controller.prototype.changeSubject = function (id, subject) {
        var self = this;

        self.model.update(id, { subject: subject }, function () {
            self._filter(true);
        });
    };

    /**
     * 把某一条与当前可见的相邻条目交换在全清单中的位置。
     *
     * @param {number} id 条目 id
     * @param {number} direction -1 上移 / 1 下移
     */
    Controller.prototype.moveItem = function (id, direction) {
        var self = this;

        self._readAll(function (todos) {
            var visible = self._visible(todos);
            var index = -1;

            for (var i = 0; i < visible.length; i++) {
                if (visible[i].id === id) {
                    index = i;
                    break;
                }
            }

            var target = index + direction;
            if (index === -1 || target < 0 || target >= visible.length)
                return; // 已经在边界，什么都不做

            self.model.swap(id, visible[target].id, function () {
                self._filter(true);
            });
        });
    };

    /**
     * An event to fire whenever you want to add an item. Simply pass in the event
     * object and it'll handle the DOM insertion and saving of the new item.
     */
    Controller.prototype.addItem = function (title) {
        var self = this;

        if (title.trim() === "")
            return;

        self.model.create(title, function () {
            self.view.render("clearNewTodo");
            self._filter(true);
        });
    };

    /*
     * Triggers the item editing mode.
     */
    Controller.prototype.editItem = function (id) {
        var self = this;
        self.model.read(id, function (data) {
            self.view.render("editItem", { id: id, title: data[0].title });
        });
    };

    /*
     * Finishes the item editing mode successfully.
     */
    Controller.prototype.editItemSave = function (id, title) {
        var self = this;
        title = title.trim();

        if (title.length !== 0) {
            self.model.update(id, { title: title }, function () {
                self.view.render("editItemDone", { id: id, title: title });
            });
        } else {
            self.removeItem(id);
        }
    };

    /*
     * Cancels the item editing mode.
     */
    Controller.prototype.editItemCancel = function (id) {
        var self = this;
        self.model.read(id, function (data) {
            self.view.render("editItemDone", { id: id, title: data[0].title });
        });
    };

    /**
     * By giving it an ID it'll find the DOM element matching that ID,
     * remove it from the DOM and also remove it from storage.
     *
     * @param {number} id The ID of the item to remove from the DOM and
     * storage
     */
    Controller.prototype.removeItem = function (id) {
        var self = this;
        self.model.remove(id, function () {
            self.view.render("removeItem", id);
        });

        self._filter();
    };

    /**
     * Will remove all completed items from the DOM and storage.
     */
    Controller.prototype.removeCompletedItems = function () {
        var self = this;
        self.model.read({ completed: true }, function (data) {
            data.forEach(function (item) {
                self.removeItem(item.id);
            });
        });

        self._filter();
    };

    /**
     * Give it an ID of a model and a checkbox and it will update the item
     * in storage based on the checkbox's state.
     *
     * @param {number} id The ID of the element to complete or uncomplete
     * @param {object} checkbox The checkbox to check the state of complete
     *                          or not
     * @param {boolean|undefined} silent Prevent re-filtering the todo items
     */
    Controller.prototype.toggleComplete = function (id, completed, silent) {
        var self = this;
        self.model.update(id, { completed: completed }, function () {
            self.view.render("elementComplete", {
                id: id,
                completed: completed,
            });
        });

        if (!silent)
            self._filter();
    };

    /**
     * Will toggle ALL checkboxes' on/off state and completeness of models.
     * Just pass in the event object.
     */
    Controller.prototype.toggleAll = function (completed) {
        var self = this;
        self.model.read({ completed: !completed }, function (data) {
            data.forEach(function (item) {
                self.toggleComplete(item.id, completed, true);
            });
        });

        self._filter();
    };

    /**
     * Updates the pieces of the page which change depending on the remaining
     * number of todos.
     */
    Controller.prototype._updateCount = function () {
        var self = this;
        self.model.getCount(function (todos) {
            self.view.render("updateElementCount", todos.active);
            self.view.render("clearCompletedButton", {
                completed: todos.completed,
                visible: todos.completed > 0,
            });

            self.view.render("toggleAll", { checked: todos.completed === todos.total });
            self.view.render("contentBlockVisibility", { visible: todos.total > 0 });
        });
    };

    /**
     * Re-filters the todo items, based on the active route.
     * @param {boolean|undefined} force  forces a re-painting of todo items.
     */
    Controller.prototype._filter = function (force) {
        var activeRoute = this._activeRoute.charAt(0).toUpperCase() + this._activeRoute.substr(1);

        // Update the elements on the page, which change with each completed todo
        this._updateCount();

        // 参考实现：筛选条件（完成状态 + 科目）任一变化都要重绘，
        // 因此这里不再做「路由没变就跳过」的优化。
        this.showEntries();

        this._lastActiveRoute = activeRoute;
    };

    /**
     * Simply updates the filter nav's selected states
     */
    Controller.prototype._updateFilterState = function (currentPage) {
        // Store a reference to the active route, allowing us to re-filter todo
        // items as they are marked complete or incomplete.
        // 统一归一化为 "All" / "Active" / "Completed"，供 _visible 使用
        this._activeRoute = currentPage === ""
            ? "All"
            : currentPage.charAt(0).toUpperCase() + currentPage.substr(1);

        this._filter();

        this.view.render("setFilter", currentPage);
    };

    // Export to window
    window.app = window.app || {};
    window.app.Controller = Controller;
})(window);
