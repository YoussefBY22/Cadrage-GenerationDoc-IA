import { expect, request, test, type APIRequestContext, type Page } from "@playwright/test";
import path from "node:path";
import { readFileSync } from "node:fs";

const API = `http://localhost:${process.env.E2E_API_PORT ?? "8001"}/api/v1`;
const PASSWORD = "demo-parcours-2026";
const CORPUS = path.resolve(__dirname, "..", ".e2e", "corpus");
const IMG = path.resolve(__dirname, "..", "..", "docs", "img");
const SECTIONS = ["contexte", "objectifs", "livrables", "calendrier", "profil", "evaluation"];

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Mot de passe").fill(PASSWORD);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page).toHaveURL(/\/dossiers$/);
}

async function logout(page: Page) {
  await page.getByRole("button", { name: "Quitter" }).click();
  await expect(page).toHaveURL(/\/login$/);
}

async function apiLogin(ctx: APIRequestContext, email: string) {
  const r = await ctx.post(`${API}/auth/login`, { data: { email, password: PASSWORD } });
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  return { headers: { Authorization: `Bearer ${body.token}` }, id: body.user.id as string };
}

/** Deux autres dossiers déjà avancés, pour que le tableau de bord soit parlant. */
async function seedOthers(ctx: APIRequestContext) {
  const { headers } = await apiLogin(ctx, "consultante@demo.local");
  const others = [
    { inst: "ARV", client: "Régie intercommunale d'Arvaux", name: "Schéma directeur — réseau", files: ["diagnostic.docx", "priorites.docx"], validate: 3 },
    { inst: "LOR", client: "Syndicat des eaux de Lorance", name: "Plan de continuité d'activité", files: ["diagnostic.docx"], validate: 0 },
  ];
  for (const o of others) {
    const d = await ctx.post(`${API}/dossiers`, { headers, data: { name: o.name, client_name: o.client } });
    const id = (await d.json()).id as string;
    for (const f of o.files) {
      const file = path.join(CORPUS, o.inst, f);
      await ctx.post(`${API}/dossiers/${id}/documents`, {
        headers,
        multipart: { file: { name: f, mimeType: "application/octet-stream", buffer: readFileSync(file) } },
      });
    }
    const ext = await (await ctx.post(`${API}/dossiers/${id}/findings:extract`, { headers })).json();
    for (const f of (ext.findings as { id: string }[]).slice(0, o.validate)) {
      await ctx.patch(`${API}/findings/${f.id}`, { headers, data: { validated: true } });
    }
  }
}

test("parcours complet : connexion → dossier → import → constats → ToR → approbation → export", async ({ page }) => {
  const shot = (name: string) => page.screenshot({ path: path.join(IMG, name), fullPage: false });

  // --- connexion (et bascule de langue)
  await login(page, "consultante@demo.local");
  await page.getByRole("button", { name: "EN" }).first().click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await page.getByRole("button", { name: "FR" }).first().click();
  await expect(page.getByRole("heading", { name: "Tableau de bord" })).toBeVisible();
  await expect(page.getByText("Projet étudiant — non affilié à EY")).toBeVisible();

  // --- dossier
  await page.getByRole("button", { name: "Nouveau" }).first().click();
  await page.getByLabel("Nom du dossier").fill("Schéma directeur de l'eau");
  await page.getByLabel("Client").fill("Agence nationale de l'eau de Valmont");
  await page.getByRole("button", { name: "Créer" }).click();
  await page.getByRole("link", { name: /Ouvrir Schéma directeur de l'eau/ }).click();
  await expect(page).toHaveURL(/\/dossiers\/[\w-]+$/);
  const dossierId = page.url().split("/").pop()!;
  await expect(page.getByRole("heading", { name: "Schéma directeur de l'eau" })).toBeVisible();

  // --- import
  await page
    .getByTestId("file-input")
    .setInputFiles(["diagnostic.docx", "priorites.docx", "atelier.pptx"].map((f) => path.join(CORPUS, "VAL", f)));
  await expect(page.locator("tbody tr")).toHaveCount(3);

  // --- constats : extraction, validation (le dernier reste à valider), source dans le panneau de droite
  await page.getByTestId("step-findings").click();
  await expect(page.getByRole("heading", { name: "Constats" })).toBeVisible();
  await page.getByRole("button", { name: "Extraire" }).click();
  const boxes = page.getByRole("checkbox");
  await expect(boxes.first()).toBeVisible();
  const n = await boxes.count();
  expect(n).toBeGreaterThan(2);
  for (let i = 0; i < n - 1; i++) {
    await boxes.nth(i).click();
    await expect(boxes.nth(i)).toBeChecked();
  }
  await page.locator("button.link").first().click();
  await expect(page.getByRole("complementary", { name: "Source" }).locator("pre")).toBeVisible();
  await page.mouse.move(0, 0);
  await shot("constats.png");

  // --- feuille de route
  await page.getByRole("link", { name: "Documents" }).click();
  await page.getByTestId("step-roadmap").click();
  await expect(page).toHaveURL(/\/deliverables\/[\w-]+\/roadmap$/);
  await expect(page.locator("tbody tr").first()).toBeVisible();
  // durées saisies puis recalcul (PATCH de la feuille de route)
  const durations = page.getByLabel(/Durée/);
  await durations.nth(0).fill("8");
  await durations.nth(1).fill("12");
  const patched = page.waitForResponse((r) => r.url().endsWith("/roadmap") && r.request().method() === "PATCH" && r.ok());
  await page.getByRole("button", { name: "Recalculer" }).click();
  await patched;
  await expect(page.getByLabel(/Durée/).nth(1)).toHaveValue("12");
  await page.mouse.move(0, 0);
  await shot("feuille-de-route.png");

  // --- ToR : génération section par section, avec vérification
  await page.getByRole("link", { name: "Documents" }).click();
  await page.getByTestId("step-tor").click();
  await expect(page).toHaveURL(/\/deliverables\/[\w-]+$/);
  const torUrl = page.url();
  for (const key of SECTIONS) {
    const section = page.getByTestId(`section-${key}`);
    const gen = section.getByRole("button", { name: "Générer" });
    const done = page.waitForResponse((r) => r.url().includes(`/sections/${key}:generate`) && r.ok());
    await gen.click();
    await done;
    await expect(gen).toBeEnabled();
  }
  await expect(page.locator("[data-sentence]").first()).toBeVisible();
  await page.locator("[data-source]").first().click();
  await expect(page.getByRole("complementary", { name: "Source" }).locator("pre")).toBeVisible();
  await page.mouse.move(0, 0);
  await shot("editeur.png");

  // --- tableau de bord du dossier (étapes terminées)
  await page.getByRole("link", { name: "Documents" }).click();
  await expect(page.getByTestId("step-tor")).toContainText("Ouvrir");
  await page.mouse.move(0, 0);
  await shot("dossier.png");

  // --- relecture puis approbation par une autre personne
  await page.goto(torUrl);
  await page.getByRole("button", { name: "Soumettre à relecture" }).click();
  await expect(page.getByTestId("state")).toHaveText("Relu");
  const ctx = await request.newContext();
  const consultant = await apiLogin(ctx, "consultante@demo.local");
  const reviewer = await apiLogin(ctx, "relecteur@demo.local");
  const add = await ctx.post(`${API}/dossiers/${dossierId}/members`, {
    headers: consultant.headers,
    data: { user_id: reviewer.id, role: "reviewer" },
  });
  expect(add.ok()).toBeTruthy();
  await logout(page);
  await login(page, "relecteur@demo.local");
  await page.goto(torUrl);
  await page.getByRole("button", { name: "Approuver" }).click();
  await expect(page.getByTestId("state")).toHaveText("Approuvé");

  // --- exports
  for (const fmt of ["DOCX", "PPTX"]) {
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: fmt, exact: true }).click();
    expect((await download).suggestedFilename().toLowerCase()).toContain(fmt.toLowerCase());
  }

  // --- tableau de bord rempli (captures avec le consultant)
  await seedOthers(ctx);
  await logout(page);
  await login(page, "consultante@demo.local");
  await expect(page.getByRole("link", { name: /Ouvrir Plan de continuité/ })).toBeVisible();
  await expect(page.locator(".kpi-value").nth(1)).not.toHaveText("0");
  await page.waitForFunction(() => !document.body.innerText.includes("–"));
  await page.mouse.move(0, 0);
  await shot("tableau-de-bord.png");
});
