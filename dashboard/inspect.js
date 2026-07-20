import puppeteer from 'puppeteer';

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  await page.goto('http://localhost:5174');
  await page.waitForSelector('#about');

  const aboutBox = await page.evaluate(() => {
    const h2 = document.querySelector('#about h2');
    const p = document.querySelector('#about h2 + p');
    return {
      h2: {
        height: h2.offsetHeight,
        lineHeight: window.getComputedStyle(h2).lineHeight,
        marginTop: window.getComputedStyle(h2).marginTop,
        marginBottom: window.getComputedStyle(h2).marginBottom,
        top: h2.getBoundingClientRect().top
      },
      p: {
        height: p.offsetHeight,
        lineHeight: window.getComputedStyle(p).lineHeight,
        marginTop: window.getComputedStyle(p).marginTop,
        marginBottom: window.getComputedStyle(p).marginBottom,
        top: p.getBoundingClientRect().top
      }
    };
  });
  console.log(JSON.stringify(aboutBox, null, 2));
  await browser.close();
})();
