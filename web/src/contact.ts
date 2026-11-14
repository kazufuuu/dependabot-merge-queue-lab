import { differenceInCalendarDays, format } from "date-fns";
import { z } from "zod";

export const ContactSchema = z.object({
  name: z.string().trim().min(1),
  email: z.email(),
  lastContactedAt: z.iso.datetime().optional(),
});

export type Contact = z.infer<typeof ContactSchema>;

export function parseContact(input: unknown): Contact {
  return ContactSchema.parse(input);
}

export function fieldErrors(input: unknown): string[] {
  const result = ContactSchema.safeParse(input);
  if (result.success) return [];
  return result.error.issues.map((issue) => issue.path.join("."));
}

export function lastContactedLabel(contact: Contact, now: Date): string {
  if (!contact.lastContactedAt) return "未連絡";
  const at = new Date(contact.lastContactedAt);
  const days = differenceInCalendarDays(now, at);
  if (days === 0) return "今日";
  if (days < 7) return `${days} 日前`;
  return format(at, "yyyy-MM-dd");
}
