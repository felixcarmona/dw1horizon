// Install puppeteer-core locally, or point PUPPETEER_MODULE at its module URL.
export default (await import(process.env.PUPPETEER_MODULE || 'puppeteer-core')).default;
