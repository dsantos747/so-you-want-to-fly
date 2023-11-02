import "./globals.css";
import { DM_sans } from "./fonts";
import "@fortawesome/fontawesome-svg-core/styles.css";
import { config } from "@fortawesome/fontawesome-svg-core";
config.autoAddCss = false;

export const metadata = {
  title: "Eco-Flyer",
  description: "Book your next holiday with the planet in mind",
  generator: "Next.js",
  applicationName: "Eco-Flyer",
  authors: [{ name: "Daniel Santos", url: "https://github.com/dsantos747" }],
  keywords: ["flights", "emissions", "environment", "travel", "low emissions"],
  creator: "Daniel Santos",
};

async function wakeUpServer() {
  try {
    // const baseUrl = process.env.API_URL;
    // console.log("ping base url is ", baseUrl);
    const response = await fetch(`https://eco-flyer.vercel.app/api/index/api/ping`);
    // const response = await fetch(`${baseUrl}/api/ping`);
    if (response.ok) {
      console.log("flask server awake");
    } else {
      console.log("error code p1");
    }
  } catch (error) {
    console.log("error code p2");
  }
}

export default function RootLayout({ children }) {
  // wakeUpServer();
  return (
    <html lang="en">
      <body className={DM_sans.className}>{children}</body>
    </html>
  );
}
