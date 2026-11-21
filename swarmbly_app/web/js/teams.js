/* Teams (3.5, D-019): stored plan templates.

   A team is edited here and run from the chat composer. The view only talks
   to the local API: nothing is sent by opening, saving or listing a team. */
"use strict";

const TeamsView = (() => {
  const { h, clear, t, chip, button, select } = UI;
  const ROLES = ["", "search", "corpus", "large_model", "reasoner"];
  let root;
  let data = null;
  const els = {};

  function init(el) {
    root = el;
    build();
    App.onEvent(onEvent);
  }

  function build() {
    clear(root);
    els.list = h("div");
    UI.append(root,
      h("header.view-head",
        h("h1.view-title", t("teams.title")),
        h("div.view-actions",
          button(t("teams.create"), () => openEditor(null), "primary small"))),
      h("p.view-lede", t("teams.lede")),
      h("section.panel", els.list));
  }

  function show() { refresh(); }

  function onEvent(event) {
    if (event.type === "app.swarm") return;
  }

  async function refresh() {
    try { data = await Api.get("/api/teams"); }
    catch (err) { data = { teams: [], error: err.message }; }
    render();
  }

  function render() {
    clear(els.list);
    if (data?.error) {
      els.list.appendChild(h("p.note", t("teams.loadFailed").replace("{e}", data.error)));
      return;
    }
    const teams = data?.teams || [];
    if (!teams.length) {
      els.list.appendChild(h("p.empty", t("teams.none")));
      return;
    }
    for (const team of teams) els.list.appendChild(teamCard(team));
    els.list.appendChild(h("p.muted.small",
      t("teams.storage").replace("{path}", (data?.storage?.project || data?.storage?.user) || "—")));
  }

  function teamCard(team) {
    const actions = [
      button(t("teams.use"), () => useInChat(team), "small"),
    ];
    if (team.builtin) {
      actions.push(button(t("teams.duplicate"), () => duplicate(team), "ghost small"));
    } else {
      actions.push(button(t("teams.edit"), () => openEditor(team), "ghost small"));
      actions.push(button(t("teams.delete"), () => remove(team), "ghost small danger"));
    }
    const steps = h("ol.step-list", (team.steps || []).map((step) => h("li",
      h("span.step-name", step.name),
      step.role ? chip(roleLabel(step.role)) : null,
      step.depends_on?.length
        ? h("span.muted.small", ` ${t("teams.after")} ${
          step.depends_on.map((dep) => (team.steps.find((s) => s.id === dep) || {}).name || dep)
            .join(", ")}`)
        : null,
      h("p.muted.small.step-instruction", step.instruction))));
    return h("div.circle-item.team-item",
      h("div.circle-head",
        h("h3", team.name),
        team.builtin ? chip(t("teams.builtin")) : chip(t("teams.own")),
        team.project_id ? chip(t("teams.project")) : null),
      team.description ? h("p.muted", team.description) : null,
      steps,
      h("div.form-actions", actions));
  }

  function roleLabel(role) { return t(`teams.role.${role}`, role); }

  function blankStep(number) {
    return { id: `s${number}`, name: "", role: "", instruction: "", depends_on: [] };
  }

  function reindex(steps) {
    const map = {};
    const next = steps.map((step, index) => {
      const id = `s${index + 1}`;
      map[step.id] = id;
      return { ...step, id };
    });
    for (const step of next) {
      step.depends_on = [...new Set((step.depends_on || [])
        .map((dep) => map[dep]).filter(Boolean))];
    }
    return next;
  }

  function openEditor(existing) {
    const name = h("input.text", { type: "text", value: existing?.name || "",
      "aria-label": t("teams.name") });
    const description = h("textarea.text", { rows: 2,
      "aria-label": t("teams.description") });
    description.value = existing?.description || "";
    let steps = existing
      ? existing.steps.map((step) => ({ ...step,
        depends_on: [...(step.depends_on || [])] }))
      : [blankStep(1)];
    const list = h("div.form-stack");
    const body = h("div.form-stack",
      h("label.stack", h("span", t("teams.name")), name),
      h("label.stack", h("span", t("teams.description")), description),
      h("p.muted.small", t("teams.requestHint")),
      list);
    function drawSteps() {
      clear(list);
      steps.forEach((step, index) => list.appendChild(stepEditor(step, index)));
      list.appendChild(h("div.form-actions",
        button(t("teams.addStep"), () => {
          steps.push(blankStep(steps.length + 1));
          drawSteps();
        }, "ghost small")));
    }
    function stepEditor(step, index) {
      const stepName = h("input.text", { type: "text", value: step.name,
        placeholder: t("teams.stepName"), "aria-label": t("teams.stepName") });
      stepName.addEventListener("input", () => { step.name = stepName.value; });
      const instruction = h("textarea.text", { rows: 4,
        placeholder: t("teams.instruction"), "aria-label": t("teams.instruction") });
      instruction.value = step.instruction;
      instruction.addEventListener("input", () => { step.instruction = instruction.value; });
      const role = select(ROLES.map((value) => ({
        value, label: value ? roleLabel(value) : t("teams.role.none") })),
        step.role, (value) => { step.role = value; },
        { "aria-label": t("teams.roleLabel") });
      const deps = h("div.checks");
      steps.slice(0, index).forEach((earlier) => {
        const box = h("input", { type: "checkbox", value: earlier.id });
        box.checked = (step.depends_on || []).includes(earlier.id);
        box.addEventListener("change", () => {
          const set = new Set(step.depends_on || []);
          if (box.checked) set.add(earlier.id); else set.delete(earlier.id);
          step.depends_on = [...set];
        });
        deps.appendChild(h("label.check", box,
          h("span", earlier.name || t("teams.unnamedStep"))));
      });
      const remove = button(t("teams.removeStep"), () => {
        steps = reindex(steps.filter((item) => item !== step));
        drawSteps();
      }, "ghost small danger", { disabled: steps.length <= 1 });
      return h("div.card.step-editor",
        h("div.circle-head",
          h("h4", t("teams.step").replace("{n}", index + 1)),
          remove),
        h("label.stack", h("span", t("teams.stepName")), stepName),
        h("label.stack", h("span", t("teams.roleLabel")), role),
        h("label.stack", h("span", t("teams.instruction")), instruction),
        deps.childElementCount
          ? h("div.stack", h("span.muted.small", t("teams.depends")), deps)
          : null);
    }
    drawSteps();
    UI.modal(existing ? t("teams.editTitle") : t("teams.createTitle"), body, [
      { label: t("common.cancel"), value: false, kind: "ghost" },
      { label: t("teams.save"), value: true, kind: "primary" },
    ]).then(async (ok) => {
      if (!ok) return;
      const clean = steps.map((step, index) => ({
        id: `s${index + 1}`, name: step.name.trim(),
        instruction: step.instruction.trim(), role: step.role,
        depends_on: step.depends_on || [] }));
      if (!name.value.trim()) return UI.toast(t("teams.nameRequired"), "error");
      if (clean.some((step) => !step.name || !step.instruction)) {
        return UI.toast(t("teams.stepsRequired"), "error");
      }
      if (!clean.some((step) => step.instruction.includes("{request}"))) {
        return UI.toast(t("teams.placeholderRequired"), "error");
      }
      try {
        const payload = { name: name.value.trim(),
          description: description.value.trim(), steps: clean,
          project_id: data?.project_id || "" };
        if (existing?.builtin) {
          await Api.post(`/api/teams/${encodeURIComponent(existing.id)}/duplicate`,
            { name: payload.name, project_id: payload.project_id });
        } else if (existing) {
          await Api.put(`/api/teams/${encodeURIComponent(existing.id)}`, payload);
        } else {
          await Api.post("/api/teams", payload);
        }
        UI.toast(t("teams.saved"), "ok");
        await Chat.refreshTeams?.();
        await refresh();
      } catch (err) { UI.toast(err.message, "error"); }
    });
  }

  async function duplicate(team) {
    const name = h("input.text", { type: "text",
      value: `${team.name} (${t("teams.copySuffix")})`, "aria-label": t("teams.name") });
    const ok = await UI.modal(t("teams.duplicate"), h("div.form-stack",
      h("label.stack", h("span", t("teams.name")), name),
      h("p.muted.small", t("teams.duplicateHint"))), [
      { label: t("common.cancel"), value: false, kind: "ghost" },
      { label: t("teams.duplicate"), value: true, kind: "primary" }]);
    if (!ok || !name.value.trim()) return;
    try {
      await Api.post(`/api/teams/${encodeURIComponent(team.id)}/duplicate`,
        { name: name.value.trim(), project_id: data?.project_id || "" });
      UI.toast(t("teams.saved"), "ok");
      await Chat.refreshTeams?.();
      await refresh();
    } catch (err) { UI.toast(err.message, "error"); }
  }

  async function remove(team) {
    const ok = await UI.modal(t("teams.delete"), h("div.form-stack",
      h("p", t("teams.deleteConfirm").replace("{name}", team.name)),
      h("p.muted.small", t("teams.deleteHint"))), [
      { label: t("common.cancel"), value: false, kind: "ghost" },
      { label: t("teams.delete"), value: true, kind: "danger" }]);
    if (!ok) return;
    try {
      await Api.del(`/api/teams/${encodeURIComponent(team.id)}`);
      UI.toast(t("teams.deleted"), "ok");
      await Chat.refreshTeams?.();
      await refresh();
    } catch (err) { UI.toast(err.message, "error"); }
  }

  async function useInChat(team) {
    await Chat.useTeam?.(team.id);
    App.navigate("chat");
    UI.toast(t("teams.picked").replace("{name}", team.name), "ok");
  }

  function relabel() { build(); render(); }

  return { init, show, relabel };
})();

App.register("teams", TeamsView);
