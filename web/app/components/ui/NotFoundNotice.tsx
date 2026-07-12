import { Container } from "./Container";

/** Shared "no data" placeholder used by league / round / match pages. */
export function NotFoundNotice({ message }: { message: string }) {
  return (
    <Container className="py-16">
      <p className="lbl text-red">{message}</p>
    </Container>
  );
}
