/* jshint laxbreak:true */
(function (window) {
    "use strict";

    var htmlEscapes = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
        "`": "&#x60;",
    };

    var escapeHtmlChar = function (chr) {
        return htmlEscapes[chr];
    };

    var reUnescapedHtml = /[&<>"'`]/g;
    var reHasUnescapedHtml = new RegExp(reUnescapedHtml.source);

    var escape = function (string) {
        return string && reHasUnescapedHtml.test(string) ? string.replace(reUnescapedHtml, escapeHtmlChar) : string;
    };

    // 科目取值与中文标签（命题方提供，固定不可改）
    var SUBJECTS = [
        { value: "unassigned", label: "未分类" },
        { value: "chinese", label: "语文" },
        { value: "math", label: "数学" },
        { value: "english", label: "英语" },
    ];

    var subjectOptions = function (current) {
        var value = current || "unassigned";
        var html = "";

        for (var i = 0; i < SUBJECTS.length; i++) {
            html += '<option value="' + SUBJECTS[i].value + '"'
                + (SUBJECTS[i].value === value ? " selected" : "")
                + ">" + SUBJECTS[i].label + "</option>";
        }

        return html;
    };

    /**
     * Sets up defaults for all the Template methods such as a default template
     *
     * @constructor
     */
    function Template() {
        this.defaultTemplate
            = '<li data-id="{{id}}" class="{{completed}}">'
            + '<div class="view">'
            + '<input class="toggle" type="checkbox" {{checked}}>'
            + "<label>{{title}}</label>"
            + '<select class="task-subject" aria-label="科目">{{subjectOptions}}</select>'
            + '<button class="move-up" type="button" aria-label="上移">上移</button>'
            + '<button class="move-down" type="button" aria-label="下移">下移</button>'
            + '<button class="destroy"></button>'
            + "</div>"
            + "</li>";
    }

    /**
     * Creates an <li> HTML string and returns it for placement in your app.
     *
     * NOTE: In real life you should be using a templating engine such as Mustache
     * or Handlebars, however, this is a vanilla JS example.
     *
     * @param {object} data The object containing keys you want to find in the
     *                      template to replace.
     * @returns {string} HTML String of an <li> element
     *
     * @example
     * view.show({
     *    id: 1,
     *    title: "Hello World",
     *    completed: 0,
     * });
     */
    Template.prototype.show = function (data) {
        var i, l;
        var view = "";

        for (i = 0, l = data.length; i < l; i++) {
            var template = this.defaultTemplate;
            var completed = "";
            var checked = "";

            if (data[i].completed) {
                completed = "completed";
                checked = "checked";
            }

            template = template.replace("{{id}}", data[i].id);
            template = template.replace("{{title}}", escape(data[i].title));
            template = template.replace("{{completed}}", completed);
            template = template.replace("{{checked}}", checked);
            template = template.replace("{{subjectOptions}}", subjectOptions(data[i].subject));

            view = view + template;
        }

        return view;
    };

    /**
     * Displays a counter of how many to dos are left to complete
     *
     * @param {number} activeTodos The number of active todos.
     * @returns {string} String containing the count
     */
    Template.prototype.itemCounter = function (activeTodos) {
        return `<strong>${activeTodos}</strong> 项未完成`;
    };

    /**
     * Updates the text within the "Clear completed" button
     *
     * @param  {[type]} completedTodos The number of completed todos.
     * @returns {string} String containing the count
     */
    Template.prototype.clearCompletedButton = function (completedTodos) {
        if (completedTodos > 0)
            return "清理已完成";
        else
            return "";
    };

    // Export to window
    window.app = window.app || {};
    window.app.Template = Template;
})(window);
