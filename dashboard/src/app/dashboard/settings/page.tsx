import { getRepoSettings } from "@/lib/data";
import { SettingsClient } from "./settings-client";

export const metadata = { title: "Marginalia — Repos & rules" };

export default async function SettingsPage() {
  const repos = await getRepoSettings();
  return <SettingsClient repos={repos} />;
}