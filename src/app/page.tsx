import { redirect } from "next/navigation";

/** M1: single landing — role-specific home can diverge in later milestones */
export default function HomePage() {
  redirect("/command-center");
}
