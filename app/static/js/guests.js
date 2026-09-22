(function () {
  "use strict";

  var list = document.getElementById("lista-convidados");
  var addButton = document.getElementById("adicionar-convidado");
  if (!list || !addButton) {
    return;
  }

  var counter = 0;

  function nextId() {
    counter += 1;
    return "guest-name-" + counter;
  }

  function focusRow(row) {
    if (!row) {
      addButton.focus();
      return;
    }
    var input = row.querySelector("input[name='guest_names']");
    if (input) {
      input.focus();
    } else {
      addButton.focus();
    }
  }

  function bindRemove(button, row) {
    button.addEventListener("click", function () {
      var next = row.nextElementSibling;
      var previous = row.previousElementSibling;
      row.remove();
      focusRow(next || previous);
    });
  }

  function addRow(value, shouldFocus) {
    var id = nextId();
    var item = document.createElement("li");
    item.className = "guest-row d-flex gap-2 mb-2 align-items-end";

    var field = document.createElement("div");
    field.className = "flex-grow-1";

    var label = document.createElement("label");
    label.className = "form-label mb-1";
    label.htmlFor = id;
    label.textContent = "Nome do convidado";

    var input = document.createElement("input");
    input.type = "text";
    input.name = "guest_names";
    input.id = id;
    input.className = "form-control";
    input.value = value || "";
    input.maxLength = 120;
    input.autocomplete = "name";

    var remove = document.createElement("button");
    remove.type = "button";
    remove.className = "btn btn-outline-danger";
    remove.textContent = "Remover";

    field.appendChild(label);
    field.appendChild(input);
    item.appendChild(field);
    item.appendChild(remove);
    list.appendChild(item);
    bindRemove(remove, item);

    if (shouldFocus) {
      input.focus();
    }
  }

  var existing = list.querySelectorAll(".guest-row");
  for (var i = 0; i < existing.length; i += 1) {
    var row = existing[i];
    var current = row.querySelector("input[name='guest_names']");
    var button = row.querySelector("button");
    if (current && current.id.indexOf("guest-name-") === 0) {
      var numeric = parseInt(current.id.replace("guest-name-", ""), 10);
      if (!isNaN(numeric) && numeric > counter) {
        counter = numeric;
      }
    }
    if (button) {
      bindRemove(button, row);
    }
  }

  addButton.addEventListener("click", function () {
    addRow("", true);
  });
})();
